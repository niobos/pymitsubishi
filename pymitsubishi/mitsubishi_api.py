#!/usr/bin/env python3
"""
Mitsubishi Air Conditioner API Communication Layer

This module handles all HTTP communication, encryption, and decryption
for Mitsubishi MAC-577IF-2E devices.
"""

import base64
import re
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any
import logging

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter, Retry

# Constants from the working implementation
KEY_SIZE = 16
STATIC_KEY = b"unregistered\0\0\0\0"

logger = logging.getLogger(__name__)


class MitsubishiAPI:
    """Handles all API communication with Mitsubishi AC devices"""
    
    def __init__(
            self,
            device_host_port: str,
            encryption_key: bytes = STATIC_KEY,
            admin_username: str = "admin",
            admin_password: str = "me1debug@0567"
    ):
        self.device_host_port = device_host_port

        self.encryption_key = encryption_key
        if len(self.encryption_key) != KEY_SIZE:
            self.encryption_key += (KEY_SIZE - len(self.encryption_key)) * b'\0'  # pad with NULL-bytes
            self.encryption_key = self.encryption_key[0:KEY_SIZE]  # trim when too long

        self.admin_username = admin_username
        self.admin_password = admin_password
        self.session = requests.Session()

        retries = Retry(total=2, backoff_factor=1)
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def encrypt_payload(self, payload: str, iv: bytes = None) -> str:
        """Encrypt payload using same method as TypeScript implementation"""
        if iv is None:  # Allow passing in IV for testing purposes
            iv = get_random_bytes(KEY_SIZE)

        # Encrypt using AES CBC with zero padding
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        
        payload_bytes = payload.encode('utf-8')
        padded_payload = pad(payload_bytes, KEY_SIZE, 'iso7816')

        encrypted = cipher.encrypt(padded_payload)
        
        return base64.b64encode(iv + encrypted).decode('utf-8')

    def decrypt_payload(self, payload_b64: str) -> Optional[str]:
        # Convert base64 to hex string
        encrypted = base64.b64decode(payload_b64)

        logger.debug(f"Base64 payload length: {len(payload_b64)}")

        iv = encrypted[:KEY_SIZE]
        encrypted_data = encrypted[KEY_SIZE:]

        logger.debug(f"IV: {iv.hex()}")

        logger.debug(f"Encrypted data length: {len(encrypted_data)}")
        logger.debug(f"Encrypted data (first 64 bytes): {encrypted_data[:64].hex()}")

        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_data)

        logger.debug(f"Decrypted raw length: {len(decrypted)}")
        logger.debug(f"Decrypted raw (first 64 bytes): {decrypted[:64]}")
        logger.debug(f"Decrypted raw (last 64 bytes): {decrypted[-64:]}")

        decrypted_clean = unpad(decrypted, KEY_SIZE, 'iso7816')

        logger.debug(f"After padding removal length: {len(decrypted_clean)}")
        logger.debug(f"Non-zero bytes at end: {decrypted_clean[-20:]}")

        # Try to decode as UTF-8
        result = decrypted_clean.decode('utf-8')  # may raise
        return result


    def make_request(self, payload_xml: str) -> Optional[str]:
        """Make HTTP request to the /smart endpoint"""
        # Encrypt the XML payload
        encrypted_payload = self.encrypt_payload(payload_xml)
        
        # Create the full XML request body
        request_body = f'<?xml version="1.0" encoding="UTF-8"?><ESV>{encrypted_payload}</ESV>'
        
        logger.debug("Request Body:")
        logger.debug(request_body)

        headers = {
            'Host': f'{self.device_host_port}',
            'Content-Type': 'text/plain; charset=UTF-8',
            'Connection': 'keep-alive',
            'Proxy-Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': 'KirigamineRemote/5.1.0 (jp.co.MitsubishiElectric.KirigamineRemote; build:3; iOS 17.5.1) Alamofire/5.9.1',
            'Accept-Language': 'zh-Hant-JP;q=1.0, ja-JP;q=0.9',
        }
        
        url = f'http://{self.device_host_port}/smart'
        
        try:
            response = self.session.post(url, data=request_body, headers=headers, timeout=2)
            
            if response.status_code == 200:
                logger.debug("Response Text:")
                logger.debug(response.text)
                try:
                    root = ET.fromstring(response.text)
                    encrypted_response = root.text
                    if encrypted_response:
                        decrypted = self.decrypt_payload(encrypted_response)
                        return decrypted
                except ET.ParseError as e:
                    logger.error(f"XML parsing error: {e}")
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None


    def send_status_request(self) -> Optional[str]:
        """Send a status request to get current device state"""
        payload_xml = '<CSV><CONNECT>ON</CONNECT></CSV>'
        return self.make_request(payload_xml)

    def send_echonet_enable(self) -> Optional[str]:
        """Send ECHONET enable command"""
        payload_xml = '<CSV><CONNECT>ON</CONNECT><ECHONET>ON</ECHONET></CSV>'
        return self.make_request(payload_xml)

    def send_hex_command(self, hex_command: str) -> Optional[str]:
        """Send a hex command to the device"""
        payload_xml = f'<CSV><CONNECT>ON</CONNECT><CODE><VALUE>{hex_command}</VALUE></CODE></CSV>'
        return self.make_request(payload_xml)

    def get_unit_info(self) -> Optional[Dict[str, Any]]:
        """Get unit information from the /unitinfo endpoint using admin credentials"""
        try:
            url = f'http://{self.device_host_port}/unitinfo'
            # Use provided password or fall back to instance default
            auth = HTTPBasicAuth(self.admin_username, self.admin_password)
            
            logger.debug(f"Fetching unit info from {url}")
            
            response = self.session.get(url, auth=auth, timeout=2)
            
            if response.status_code == 200:
                logger.debug(f"Unit info HTML response received ({len(response.text)} chars)")
                
                # Parse the HTML response to extract unit information
                return self._parse_unit_info_html(response.text)
            else:
                logger.debug(f"Unit info request failed with status {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Unit info request error: {e}")
            return None
    
    def _parse_unit_info_html(self, html_content: str) -> Dict[str, Any]:
        """Parse unit info HTML response to extract structured data"""
        unit_info = {
            'adaptor_info': {},
            'unit_info': {}
        }
        
        try:
            # Extract data using regex patterns to parse the HTML structure
            # Pattern to match <dt>Label</dt><dd>Value</dd> pairs
            pattern = r'<dt>([^<]+)</dt>\s*<dd>([^<]+)</dd>'
            matches = re.findall(pattern, html_content)
            
            logger.debug(f"Found {len(matches)} key-value pairs in HTML")
            
            # Determine which section we're in based on the order and known fields
            adaptor_fields = {
                'Adaptor name', 'Application version', 'Release version', 'Flash version',
                'Boot version', 'Common platform version', 'Test release version',
                'MAC address', 'ID', 'Manufacturing date', 'Current time', 'Channel',
                'RSSI', 'IT communication status', 'Server operation', 
                'Server communication status', 'Server communication status(HEMS)',
                'SOI communication status', 'Thermal image timestamp'
            }
            
            unit_fields = {
                'Unit type', 'IT protocol version', 'Error'
            }
            
            for key, value in matches:
                key = key.strip()
                value = value.strip()
                
                if key in adaptor_fields:
                    # Convert specific fields to appropriate types
                    if key == 'RSSI':
                        # Extract numeric value from "-25dBm" format
                        rssi_match = re.search(r'(-?\d+)', value)
                        if rssi_match:
                            unit_info['adaptor_info']['rssi_dbm'] = int(rssi_match.group(1))
                        unit_info['adaptor_info']['rssi_raw'] = value
                    elif key == 'Channel':
                        try:
                            unit_info['adaptor_info']['wifi_channel'] = int(value)
                        except ValueError:
                            unit_info['adaptor_info']['wifi_channel_raw'] = value
                    elif key == 'ID':
                        try:
                            unit_info['adaptor_info']['device_id'] = int(value)
                        except ValueError:
                            unit_info['adaptor_info']['device_id_raw'] = value
                    elif key == 'MAC address':
                        unit_info['adaptor_info']['mac_address'] = value
                    elif key == 'Manufacturing date':
                        unit_info['adaptor_info']['manufacturing_date'] = value
                    elif key == 'Current time':
                        unit_info['adaptor_info']['current_time'] = value
                    elif key == 'Adaptor name':
                        unit_info['adaptor_info']['model'] = value
                    elif key == 'Application version':
                        unit_info['adaptor_info']['app_version'] = value
                    elif key == 'Release version':
                        unit_info['adaptor_info']['release_version'] = value
                    elif key == 'Flash version':
                        unit_info['adaptor_info']['flash_version'] = value
                    elif key == 'Boot version':
                        unit_info['adaptor_info']['boot_version'] = value
                    elif key == 'Common platform version':
                        unit_info['adaptor_info']['platform_version'] = value
                    elif key == 'Test release version':
                        unit_info['adaptor_info']['test_version'] = value
                    elif key == 'IT communication status':
                        unit_info['adaptor_info']['it_comm_status'] = value
                    elif key == 'Server operation':
                        unit_info['adaptor_info']['server_operation'] = value == 'ON'
                    elif key == 'Server communication status':
                        unit_info['adaptor_info']['server_comm_status'] = value
                    elif key == 'Server communication status(HEMS)':
                        unit_info['adaptor_info']['hems_comm_status'] = value
                    elif key == 'SOI communication status':
                        unit_info['adaptor_info']['soi_comm_status'] = value
                    elif key == 'Thermal image timestamp':
                        unit_info['adaptor_info']['thermal_timestamp'] = value if value != '--' else None
                    else:
                        # Fallback: store with normalized key
                        normalized_key = key.lower().replace(' ', '_').replace('(', '').replace(')', '')
                        unit_info['adaptor_info'][normalized_key] = value
                        
                elif key in unit_fields:
                    if key == 'Unit type':
                        unit_info['unit_info']['type'] = value
                    elif key == 'IT protocol version':
                        unit_info['unit_info']['it_protocol_version'] = value
                    elif key == 'Error':
                        unit_info['unit_info']['error_code'] = value
                    else:
                        # Fallback: store with normalized key
                        normalized_key = key.lower().replace(' ', '_')
                        unit_info['unit_info'][normalized_key] = value
            
            logger.debug(f"Parsed unit info: {len(unit_info['adaptor_info'])} adaptor fields, {len(unit_info['unit_info'])} unit fields")
            
            return unit_info
            
        except Exception as e:
            logger.debug(f"Error parsing unit info HTML: {e}")
            return {'adaptor_info': {}, 'unit_info': {}, 'parse_error': str(e)}

    def close(self):
        """Close the session"""
        if self.session:
            self.session.close()
