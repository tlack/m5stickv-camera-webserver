
from CONFIG import *
from binascii import *

import json
import os
import serial
import sys
import time

class Konnector:

    n_snapshots = 0

    def _code(self):
        return open(MCU_CODE,'r').read()

    def _local_file(self, fn):
        p = str(int(time.time()))
        return os.path.join(SAVE_DIR, p + "-" + fn)

    def _wait(self, secs=None):
        time.sleep(secs or SLEEP_TIME)

    def _get(self, until=None):
        if type(until) == type(""): until = str.encode(until)
        R = b''
        start = time.time()
        while 1:
            if time.time() - start > WAIT_TIME:
                return []
            o = self.ser.read_all()
            if len(o):
                if LOG_READ: print(">",o)
                R += o
                if until:
                    if R[-1 * len(until):] == until:
                        return R
        return R

    def _put(self, data):
        if type(data) == type(""): data = str.encode(data)
        data += b'\r\n'
        if LOG_WRITE: print("<",data)
        self.ser.write(data)
        self._wait()

    def _query(self, query, until=None):
        self._put(query)
        raw = self._get(until)
        # print('_query',raw)
        if raw[-1 * len(until):] == PROMPT:
            raw = raw[:-1 * len(until)]
        raw = raw.decode()
        if "\r\nTraceback (most recent call last):\r\n" in raw:
            raise IOError(raw)
        if raw[:len(query)] == query:
            raw = raw[len(query):]
        if raw[:2] == "\r\n":
            raw = raw[2:]
        return raw

    def _eval(self, expr):
        raw = self._query(expr, PROMPT)
        return raw

    def start(self, port, baud1, baud2):
        self.code = self._code()
        self.ser = serial.Serial(port,
             baudrate=baud1,
             parity=serial.PARITY_NONE,
             stopbits=serial.STOPBITS_ONE,
             bytesize=serial.EIGHTBITS)
        if not self.ser.is_open:
            raise 'bombed'
        print('open',self.ser.name)
        self.file = KonnectorFiles(self)
        self.bootstrap()

    def eval(self, code):
        print('eval', code)
        if type(code) == type(""): code = [code]
        if len(code) > 1:
            code2 = "; ".join(code[:-1])
            res = self._eval(code2)
            # print('eval res', res)

        code2 = f"repr({code[-1]})"
        # code2 = f"print({code})"
        raw = self._eval(code2)
        if raw[:2] == "b'":
            raw = raw[2:]
            raw = raw[:-1]
        elif raw[:1] == "'":
            raw = raw[1:]
            raw = raw[:-1]
        print('eval response', raw)
        fixed = eval(str.encode(raw))
        return fixed

    def eval_binary(self, code):
        print('eval_binary', code)
        if type(code) == type(""): code = [code]
        if len(code) > 1:
            code2 = "; ".join(code[:-1])
            self._eval(code2)
        code2 = f"hexlify({code[-1]})"
        # code2 = f"print({code[-1]})"
        print('eval_binary code', code2)
        raw = self._eval(code2)
        if raw[:2] == "b'":
            raw = raw[2:]
            raw = raw[:-1]
        print('eval_binary response', raw)
        print(len(raw))
        fixed = unhexlify(str.encode(raw))
        return fixed
    
    def calibrate(self):
        results = {}
        for i in range(-2, 2+1):
            code = [
                f"sensor.set_brightness({i})",
                "x=sensor.snapshot()",
                "x.get_statistics()"
            ]
            res = self.eval(code)
            # print(res)
            self._wait()
            img = self.snapshot(f"calibrate-{i}.jpg")
            res["img"] = img
            json_fn = img["fn"].replace("jpg", "json")

            json_f = open(json_fn, "w")
            json_f.write(json.dumps(res)+"\n")
            json_f.close()
            print('json fn: ', json_fn)
            results[i] = res
            self._wait()
        return results

    def snapshot(self, fn=None):
        if not fn: fn = str(self.n_snapshots)+".jpg"
        start = time.time()
        code = [
            "sensor.set_colorbar(0)",
            "x=sensor.snapshot()",
            f"x.compress({COMPRESS})",
            "x.to_bytes()"
        ]
        raw = self.eval_binary(code)
        self._eval("del x")
        fn = self._local_file(fn)
        open(fn, 'wb').write(raw)
        self.n_snapshots += 1
        finish = time.time()
        return {'fn':fn, 'len':len(raw), 'time':finish - start}

    def tune_baud(self):
        print('setting ideal baud')
        cmd = f"from machine import UART; repl = UART.repl_uart();" + \
              f"repl.init({BAUD_PEAK}, 8, None, 1, read_buf_len=32767)"
        o = self._put(cmd)
        print('put', o)
        g = self.ser.read_all()
        print('g', g)
        time.sleep(0.3)
        print('before', self.ser.baudrate)
        self.ser.baudrate=BAUD_PEAK
        time.sleep(0.3)
        self._wait()
        self.ser.write(b'\x00\x03\x03')
        g = self.ser.read_all()
        print('after', self.ser.baudrate)
        print('tbg', g)
        # p = self._get(PROMPT)
        z = self._eval("'xyz'")
        print('z', z)
        print('baud locked')

    def bootstrap(self):
        log = self._get(b'[MAIXPY]: find ov7740\r\n')
        print('log',log)
        self._wait(BOOT_TIME)
        print('connected, breaking in..')
        self._put(b'\x03')
        p = self._get(PROMPT)
        if not len(p):
            print('died')
            sys.exit(1)
        self.tune_baud();
        self._eval("from ubinascii import *")
        b = self.file.read('boot.py')
        print('boot.py contents:')
        print(b)
        print('calibrating..')
        cal = self.calibrate()
        # print('results:\n', cal)
        p = self.snapshot("boot.jpg")
        print('storage contents:')
        print(self.file.list())

class KonnectorFiles:
    def __init__(self, kon):
        self.kon = kon

    def list(self):
        data = self.kon.eval(f"os.listdir()")
        return data

    def read(self, fname):
        data = self.kon.eval_binary(f"open('{fname}','r').read()")
        return data

    def write(self, fname, content):
        pass

def main():
    k = Konnector()
    k.start(PORT, BAUD_START, BAUD_PEAK)

main()

