# CAN to UDP converter
Convert can to UDP socket and back

## github project:
* [can_to_udp_converter]

[can_to_udp_converter]: https://github.com/mikhailk921/can_to_udp_converter

### Setup virtual device:
```bash
sudo modprobe vcan
# Create a vcan network interface with a specific name
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 up
```

### Setup real device:
```bash
sudo ip link set can0 up type can bitrate 1000000
```

### CAN interface removal:
```bash
sudo ip link del vcan0
```

### Run converter
```bash
./Converter.py -a 127.0.0.1 -d can0
```
