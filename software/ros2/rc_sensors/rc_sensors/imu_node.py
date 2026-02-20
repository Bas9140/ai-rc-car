"""
imu_node  –  MPU-6050 / GY-521 driver over I2C

Publishes:
  /imu/data  sensor_msgs/Imu  @ 100 Hz

The MPU-6050 is connected to I2C bus 1 (pins SDA/SCL).
Default I2C address: 0x68 (AD0 low).  Set AD0 high for 0x69.

Provides raw accelerometer + gyroscope data.
Orientation is not computed here; use robot_localization EKF for that.
"""

import struct
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

import smbus2


# MPU-6050 register map
_ADDR            = 0x68
_REG_PWR_MGMT_1  = 0x6B
_REG_ACCEL_XOUT  = 0x3B
_REG_GYRO_XOUT   = 0x43
_REG_WHO_AM_I    = 0x75

# Scale factors (datasheet, ±2g accel, ±250°/s gyro)
_ACCEL_SCALE = 16384.0   # LSB/g
_GYRO_SCALE  = 131.0     # LSB/°/s
_G           = 9.80665   # m/s²
_DEG2RAD     = 0.017453292519943295


class Mpu6050:
    """Minimal MPU-6050 driver using smbus2."""

    def __init__(self, bus: int = 1, addr: int = _ADDR):
        self._bus  = smbus2.SMBus(bus)
        self._addr = addr
        self._wakeup()

    def _wakeup(self):
        # Clear sleep bit in PWR_MGMT_1
        self._bus.write_byte_data(self._addr, _REG_PWR_MGMT_1, 0x00)
        time.sleep(0.1)

    def _read_words(self, reg: int, count: int) -> list:
        raw = self._bus.read_i2c_block_data(self._addr, reg, count * 2)
        values = []
        for i in range(count):
            val = struct.unpack('>h', bytes(raw[i*2:(i+1)*2]))[0]
            values.append(val)
        return values

    def read_accel_ms2(self) -> tuple:
        ax, ay, az = self._read_words(_REG_ACCEL_XOUT, 3)
        return (
            ax / _ACCEL_SCALE * _G,
            ay / _ACCEL_SCALE * _G,
            az / _ACCEL_SCALE * _G,
        )

    def read_gyro_rads(self) -> tuple:
        gx, gy, gz = self._read_words(_REG_GYRO_XOUT, 3)
        return (
            gx / _GYRO_SCALE * _DEG2RAD,
            gy / _GYRO_SCALE * _DEG2RAD,
            gz / _GYRO_SCALE * _DEG2RAD,
        )

    def close(self):
        self._bus.close()


class ImuNode(Node):

    def __init__(self):
        super().__init__('imu_node')

        self.declare_parameter('i2c_bus',    1)
        self.declare_parameter('i2c_addr',   0x68)
        self.declare_parameter('frame_id',   'imu_link')
        self.declare_parameter('rate_hz',    100.0)

        bus     = self.get_parameter('i2c_bus').value
        addr    = self.get_parameter('i2c_addr').value
        rate    = self.get_parameter('rate_hz').value
        self._frame = self.get_parameter('frame_id').value

        try:
            self._imu = Mpu6050(bus=bus, addr=addr)
            self.get_logger().info(f'MPU-6050 connected on I2C bus {bus}, addr 0x{addr:02X}')
        except Exception as e:
            self.get_logger().error(f'Cannot initialise MPU-6050: {e}')
            self._imu = None

        self._pub = self.create_publisher(Imu, '/imu/data', 10)
        self.create_timer(1.0 / rate, self._publish)

    def _publish(self):
        if self._imu is None:
            return

        try:
            ax, ay, az = self._imu.read_accel_ms2()
            gx, gy, gz = self._imu.read_gyro_rads()
        except Exception as e:
            self.get_logger().warn(f'IMU read error: {e}')
            return

        msg = Imu()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame

        msg.linear_acceleration.x = ax
        msg.linear_acceleration.y = ay
        msg.linear_acceleration.z = az

        msg.angular_velocity.x = gx
        msg.angular_velocity.y = gy
        msg.angular_velocity.z = gz

        # Orientation unknown (no magnetometer on bare MPU-6050)
        msg.orientation_covariance[0] = -1.0   # Signals: orientation invalid

        # Covariance from datasheet noise specs
        noise_a = 0.0004  # m/s² noise
        noise_g = 0.0002  # rad/s noise
        msg.linear_acceleration_covariance  = [noise_a,0,0, 0,noise_a,0, 0,0,noise_a]
        msg.angular_velocity_covariance     = [noise_g,0,0, 0,noise_g,0, 0,0,noise_g]

        self._pub.publish(msg)

    def destroy_node(self):
        if self._imu:
            self._imu.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
