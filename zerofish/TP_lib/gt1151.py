import logging
from . import epdconfig as config

_CFG_BASE        = 0x8047
_CFG_LEN         = 184          # registers 0x8047–0x80FE
_TOUCH_LEVEL_OFF = 0x8053 - _CFG_BASE  # = 12, Screen_Touch_Level

class GT_Development:
    def __init__(self):
        self.Touch = 0
        self.TouchpointFlag = 0
        self.TouchCount = 0
        self.Touchkeytrackid = [0, 1, 2, 3, 4]
        self.X = [0, 1, 2, 3, 4]
        self.Y = [0, 1, 2, 3, 4]
        self.S = [0, 1, 2, 3, 4]
    
class GT1151:
    def __init__(self):
        # e-Paper
        self.ERST = config.EPD_RST_PIN  
        self.DC = config.EPD_DC_PIN
        self.CS = config.EPD_CS_PIN
        self.BUSY = config.EPD_BUSY_PIN
        # TP
        self.TRST = config.TRST
        self.INT = config.INT

    def digital_read(self, pin):
        return config.digital_read(pin)
    
    def GT_Reset(self):
        config.digital_write(self.TRST, 1)
        config.delay_ms(100)
        config.digital_write(self.TRST, 0)
        config.delay_ms(100)
        config.digital_write(self.TRST, 1)
        config.delay_ms(100)

    def GT_Write(self, Reg, Data):
        config.i2c_writebyte(Reg, Data)

    def GT_Read(self, Reg, len):
        return config.i2c_readbyte(Reg, len)
         
    def GT_ReadVersion(self):
        buf = self.GT_Read(0x8140, 4)
        print(buf)

    def GT_ReadConfig(self):
        cfg, pos = [], 0
        while pos < _CFG_LEN:
            chunk = min(_CFG_LEN - pos, 28)
            cfg.extend(self.GT_Read(_CFG_BASE + pos, chunk))
            pos += chunk
        return cfg

    def GT_WriteConfig(self, cfg):
        checksum = (-sum(cfg)) & 0xFF
        pos = 0
        while pos < len(cfg):
            reg   = _CFG_BASE + pos
            block = cfg[pos:pos + 31]
            config.bus.write_i2c_block_data(
                config.address, (reg >> 8) & 0xFF, [reg & 0xFF] + block)
            pos += len(block)
        self.GT_Write(0x80FF, checksum)
        self.GT_Write(0x8100, 0x01)
        config.delay_ms(20)

    def GT_DumpConfig(self):
        cfg = self.GT_ReadConfig()
        logging.info('GT1151 config (%d bytes): %s', len(cfg),
                     ' '.join(f'{b:02x}' for b in cfg))
        if len(cfg) >= _TOUCH_LEVEL_OFF + 2:
            logging.info('GT1151 Screen_Touch_Level=0x%02x(%d)  Screen_Leave_Level=0x%02x(%d)',
                         cfg[_TOUCH_LEVEL_OFF],     cfg[_TOUCH_LEVEL_OFF],
                         cfg[_TOUCH_LEVEL_OFF + 1], cfg[_TOUCH_LEVEL_OFF + 1])

    def GT_SetTouchLevel(self, level):
        # WARNING: Do NOT call this. The chip ships at 0xFA (250) — already the
        # hardware maximum. Writing ANY value via GT_WriteConfig corrupts the chip
        # and makes the touch controller unresponsive until the next hard reset.
        cfg = self.GT_ReadConfig()
        if len(cfg) != _CFG_LEN:
            logging.warning('GT1151: config read failed (%d bytes)', len(cfg))
            return
        old = cfg[_TOUCH_LEVEL_OFF]
        if old == level:
            return
        cfg[_TOUCH_LEVEL_OFF] = level
        self.GT_WriteConfig(cfg)
        logging.info('GT1151 touch level %d → %d', old, level)

    def GT_Init(self):
        self.GT_Reset()
        self.GT_ReadVersion()

    def GT_Scan(self, GT_Dev, GT_Old):
        buf = []
        mask = 0x00
        
        if(GT_Dev.Touch == 1):
            GT_Dev.Touch = 0
            buf = self.GT_Read(0x814E, 1)
            
            if(buf[0]&0x80 == 0x00):
                self.GT_Write(0x814E, mask)
                config.delay_ms(10)
                
            else:
                GT_Dev.TouchpointFlag = buf[0]&0x80
                GT_Dev.TouchCount = buf[0]&0x0f
                
                if(GT_Dev.TouchCount > 5 or GT_Dev.TouchCount < 1):
                    self.GT_Write(0x814E, mask)
                    return
                    
                buf = self.GT_Read(0x814F, GT_Dev.TouchCount*8)
                self.GT_Write(0x814E, mask)
                
                GT_Old.X[0] = GT_Dev.X[0];
                GT_Old.Y[0] = GT_Dev.Y[0];
                GT_Old.S[0] = GT_Dev.S[0];
                
                for i in range(0, GT_Dev.TouchCount, 1):
                    GT_Dev.Touchkeytrackid[i] = buf[0 + 8*i] 
                    GT_Dev.X[i] = (buf[2 + 8*i] << 8) + buf[1 + 8*i]
                    GT_Dev.Y[i] = (buf[4 + 8*i] << 8) + buf[3 + 8*i]
                    GT_Dev.S[i] = (buf[6 + 8*i] << 8) + buf[5 + 8*i]

                print(GT_Dev.X[0], GT_Dev.Y[0], GT_Dev.S[0])
                