# main.py - MineGuard Smart Helmet
# Simulation Wokwi, ESP32-S3 MicroPython
import math
import struct
from time import ticks_ms, ticks_diff, sleep_ms, sleep_us
from machine import Pin, ADC, I2C
import dht

try:
    from machine import time_pulse_us
except ImportError:
    time_pulse_us = None  # absent du firmware : HC-SR04 desactive

# ---------------- BROCHES ----------------
PIN_SDA, PIN_SCL = 8, 9
PIN_GAS, PIN_TEMP = 1, 2   # PIN_TEMP = donnees du DHT22
PIN_SOS, PIN_WORN = 5, 6
PIN_TRIG, PIN_ECHO = 17, 18
PIN_BUZZER, PIN_LED_R, PIN_LED_G = 15, 16, 21  # on evite GPIO19/20 (USB)

# ---------------- SEUILS (valeurs d'exemple, a ajuster) ----------------
VREF = 3.3
GAS_WARN_DELTA = 0.30     # V au-dessus de l'air propre -> avertissement
GAS_ALARM_DELTA = 0.70    # V au-dessus de l'air propre -> alarme
TEMP_WARN_C = 35.0
TEMP_ALARM_C = 45.0
FREEFALL_G = 0.4          # sous ce module (en g) = chute libre
IMPACT_G = 2.5            # au-dessus = choc
FALL_WINDOW_MS = 3000     # choc max 3 s apres la chute libre = CHUTE (demo a la main ; reel ~1 s)
FALL_HOLD_MS = 10000      # l'alarme chute reste 10 s
IMPACT_HOLD_MS = 5000     # l'avertissement choc reste 5 s
OBSTACLE_CM = 30
MPU_ADDR = 0x68           # AD0 a GND
ACCEL_LSB_PER_G = 2048    # plage +-16 g (registre 0x1C = 0x18)

# ---------------- DRAPEAUX (un bit par cause) ----------------
GAS_W, GAS_A, TEMP_W, TEMP_A, FALL, IMPACT, SOS, NOHELM, OBST = [1 << i for i in range(9)]
NAMES = ("GAS_W", "GAS_A", "TEMP_W", "TEMP_A", "FALL", "IMPACT", "SOS", "NOHELM", "OBST")
ALARM_MASK = GAS_A | TEMP_A | FALL | SOS
LEVELS = ("OK", "WARN", "ALARM")


def make_adc(pin):
    a = ADC(Pin(pin))
    try:
        a.atten(ADC.ATTN_11DB)  # plage 0 - 3,3 V
    except Exception:
        pass
    return a


def read_v(adc, n=8):
    s = 0
    for _ in range(n):
        s += adc.read_u16()
    return s / n / 65535 * VREF


def read_dist_cm(trig, echo):
    trig.value(0)
    sleep_us(2)
    trig.value(1)
    sleep_us(10)
    trig.value(0)
    try:
        t = time_pulse_us(echo, 1, 30000)  # duree de l'echo en us
    except OSError:
        return None
    if t < 0:
        return None
    return t / 58.0  # aller-retour : 2 x d / 0,0343 cm/us


def why(flags):
    return "+".join(n for i, n in enumerate(NAMES) if flags & (1 << i)) or "-"


def fmt(v, f):
    return "NA" if v is None else f % v


def main():
    gas_adc = make_adc(PIN_GAS)
    dht_sensor = dht.DHT22(Pin(PIN_TEMP))
    sos_pin = Pin(PIN_SOS, Pin.IN, Pin.PULL_UP)
    worn_pin = Pin(PIN_WORN, Pin.IN, Pin.PULL_UP)
    trig = Pin(PIN_TRIG, Pin.OUT, value=0)
    echo = Pin(PIN_ECHO, Pin.IN)
    buzzer = Pin(PIN_BUZZER, Pin.OUT, value=0)
    led_r = Pin(PIN_LED_R, Pin.OUT, value=0)
    led_g = Pin(PIN_LED_G, Pin.OUT, value=0)

    # --- MPU6050 ---
    i2c = None
    mpu_ok = False
    try:
        i2c = I2C(0, sda=Pin(PIN_SDA), scl=Pin(PIN_SCL), freq=400000)
        if MPU_ADDR in i2c.scan():
            i2c.writeto_mem(MPU_ADDR, 0x6B, b"\x00")  # sortie du mode veille
            i2c.writeto_mem(MPU_ADDR, 0x1C, b"\x18")  # plage +-16 g
            mpu_ok = True
    except Exception as e:
        print("I2C erreur:", e)
    print("MPU6050:", "OK" if mpu_ok else "ABSENT")
    print("HC-SR04:", "OK" if time_pulse_us else "DESACTIVE")

    # --- calibration gaz : moyenne en "air propre" pendant 2 s ---
    led_r.value(1)
    led_g.value(1)
    s = 0
    for _ in range(20):
        s += read_v(gas_adc)
        sleep_ms(100)
    base = s / 20
    gas_alarm = min(base + GAS_ALARM_DELTA, 3.2)
    gas_warn = min(base + GAS_WARN_DELTA, gas_alarm - 0.1)
    print("CAL;base=%.2fV;warn=%.2fV;alarm=%.2fV" % (base, gas_warn, gas_alarm))

    # --- etat ---
    gas_v = base
    temp_c = 25.0
    g = None
    dist = None
    freefall_t = fall_t = impact_t = None
    sos_on = False
    sos_prev = 1
    sos_lock = 0
    t_mpu = t_adc = t_us = t_tx = t_dht = ticks_ms()
    last_flags = -1

    while True:
        now = ticks_ms()

        # bouton SOS : front descendant + anti-rebond 250 ms, bascule on/off
        v = sos_pin.value()
        if v == 0 and sos_prev == 1 and ticks_diff(now, sos_lock) > 250:
            sos_on = not sos_on
            sos_lock = now
        sos_prev = v

        # MPU6050 a 50 Hz : module de l'acceleration en g
        if mpu_ok and ticks_diff(now, t_mpu) >= 20:
            t_mpu = now
            try:
                raw = i2c.readfrom_mem(MPU_ADDR, 0x3B, 6)
                ax, ay, az = struct.unpack(">hhh", raw)
                g = math.sqrt(ax * ax + ay * ay + az * az) / ACCEL_LSB_PER_G
                if g < FREEFALL_G:
                    freefall_t = now
                elif g > IMPACT_G:
                    impact_t = now
                    if freefall_t is not None and ticks_diff(now, freefall_t) < FALL_WINDOW_MS:
                        fall_t = now
                        freefall_t = None
            except Exception:
                g = None

        # gaz a 5 Hz
        if ticks_diff(now, t_adc) >= 200:
            t_adc = now
            gas_v = read_v(gas_adc, 4)

        # DHT22 : une lecture toutes les 2 s maximum (limite du capteur)
        if ticks_diff(now, t_dht) >= 2000:
            t_dht = now
            try:
                dht_sensor.measure()
                temp_c = dht_sensor.temperature()
            except OSError:
                pass  # lecture ratee : on garde la derniere valeur

        # ultrasons a 4 Hz
        if time_pulse_us and ticks_diff(now, t_us) >= 250:
            t_us = now
            dist = read_dist_cm(trig, echo)

        # --- evaluation ---
        flags = 0
        if gas_v >= gas_alarm:
            flags |= GAS_A
        elif gas_v >= gas_warn:
            flags |= GAS_W
        if temp_c >= TEMP_ALARM_C:
            flags |= TEMP_A
        elif temp_c >= TEMP_WARN_C:
            flags |= TEMP_W
        if fall_t is not None and ticks_diff(now, fall_t) < FALL_HOLD_MS:
            flags |= FALL
        if impact_t is not None and ticks_diff(now, impact_t) < IMPACT_HOLD_MS:
            flags |= IMPACT
        if sos_on:
            flags |= SOS
        if worn_pin.value() == 1:  # interrupteur ouvert = casque non porte
            flags |= NOHELM
        if dist is not None and dist < OBSTACLE_CM:
            flags |= OBST

        level = 2 if flags & ALARM_MASK else (1 if flags else 0)

        # --- sorties ---
        if level == 2:
            on = (now // 150) % 2 == 0
            buzzer.value(on)
            led_r.value(on)
            led_g.value(0)
        elif level == 1:
            buzzer.value((now % 1000) < 80)
            led_r.value((now // 500) % 2 == 0)
            led_g.value(0)
        else:
            buzzer.value(0)
            led_r.value(0)
            led_g.value(1)

        # --- messages vers le terminal virtuel ---
        if flags != last_flags:
            last_flags = flags
            print("EVT;t=%d;lvl=%s;why=%s" % (now // 1000, LEVELS[level], why(flags)))
        if ticks_diff(now, t_tx) >= 1000:
            t_tx = now
            print("MG;t=%d;lvl=%s;gas=%.2fV;temp=%.1fC;g=%s;dist=%s;worn=%d;sos=%d;why=%s" % (
                now // 1000, LEVELS[level], gas_v, temp_c,
                fmt(g, "%.2f"), fmt(dist, "%.0f"),
                1 - worn_pin.value(), 1 if sos_on else 0, why(flags)))

        sleep_ms(5)


main()
