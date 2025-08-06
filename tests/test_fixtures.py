"""
Test fixtures containing sanitized real device responses for testing.

All personal information (MAC address, serial number) has been anonymized.
"""

# Real device response with sanitized MAC and serial
REAL_DEVICE_XML_RESPONSE = """<LSV><MAC>AA:BB:CC:DD:EE:FF</MAC><SERIAL>1234567890</SERIAL><CONNECTION>NOT OK</CONNECTION><VERSION>V5.2.7</VERSION><STATUS>OK</STATUS><PROFILECODE><DATA><VALUE>0300200714070000000000000000000000000000000000000000000000000000</VALUE></DATA></PROFILECODE><CODE><DATA><VALUE>ffffffffffffffffffff0202008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0302008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0402008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0502008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0602008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0702008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0802008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0902008000</VALUE></DATA></CODE><CODE><DATA><VALUE>ffffffffffffffffffff0a02008000</VALUE></DATA></CODE><PROFILECODE><DATA><VALUE>a0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0be</VALUE></DATA></PROFILECODE><PROFILECODE><DATA><VALUE>0000000000000000000000000000000000000000000000000000000000000000</VALUE></DATA></PROFILECODE><PROFILECODE><DATA><VALUE>0000000000000000000000000000000000000000000000000000000000000000</VALUE></DATA></PROFILECODE><PROFILECODE><DATA><VALUE>0000000000000000000000000000000000000000000000000000000000000000</VALUE></DATA></PROFILECODE><LED><LED1>1:30,0:30</LED1><LED2>1:30,0:30</LED2><LED3>1:30,0:30</LED3><LED4>1:5,0:45</LED4></LED><ECHONET>ON</ECHONET></LSV>"""

# Profile codes found in real device responses
SAMPLE_PROFILE_CODES = [
    "0300200714070000000000000000000000000000000000000000000000000000",  # First profile with capability flags
    "a0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0bea0be",    # Second profile with repeated pattern
    "0000000000000000000000000000000000000000000000000000000000000000",   # Empty profile codes
]

# Sample hex code values for parser testing
SAMPLE_CODE_VALUES = [
    "ffffffffffffffffffff0202008000",  # Group code 02
    "ffffffffffffffffffff0302008000",  # Group code 03  
    "ffffffffffffffffffff0402008000",  # Group code 04
    "ffffffffffffffffffff0502008000",  # Group code 05
    "ffffffffffffffffffff0602008000",  # Group code 06
    "ffffffffffffffffffff0702008000",  # Group code 07
    "ffffffffffffffffffff0802008000",  # Group code 08
    "ffffffffffffffffffff0902008000",  # Group code 09
    "ffffffffffffffffffff0a02008000",  # Group code 0a
]

