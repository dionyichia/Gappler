#!/usr/bin/env python3
"""livox_ros_driver2/CustomMsg to sensor_msgs/PointCloud2, for nav's /scan path when FAST-LIVO2 owns the LiDAR format.

The Livox driver publishes one format per run. FAST-LIVO2 needs CustomMsg (per-point times), nav's pointcloud_to_laserscan needs
PointCloud2. With odom_source:=fastlivo the driver runs CustomMsg and this node replaces qos_relay: it subscribes /livox/lidar and
publishes /cloud_relay (best effort, x y z intensity float32, same header).

It reads the raw CDR bytes and decodes them itself. rclpy decodes one 19,968-point CustomMsg in 110.6 ms, longer than the 100 ms
LiDAR period; the numpy decode below takes 0.38 ms and equals rclpy on every field (T3.5e write-up, Phase 1).

CDR layout of CustomMsg after the 4-byte encapsulation header (offsets relative to what follows it): header stamp int32 sec,
uint32 nanosec, string frame_id (uint32 length including the NUL, bytes), then timebase uint64 aligned to 8, point_num uint32,
lidar_id uint8, rsvd[3], a uint32 element count, then 20-byte points (offset_time uint32, x y z float32, reflectivity, tag, line,
one pad byte; the last point has no pad).
"""
import math
import struct

POINT_STEP = 16
FIELDS = [("x", 0), ("y", 4), ("z", 8), ("intensity", 12)]  # all FLOAT32
_STRIDE = 20


def _header(data):
    """Parse up to the point array. Returns (msg dict without points, offset of the first point, point count, view)."""
    if len(data) < 4:
        raise ValueError("shorter than the CDR encapsulation header")
    d = memoryview(data)[4:]
    if len(d) < 12:
        raise ValueError("truncated header")
    sec, nsec, n = struct.unpack_from("<iII", d, 0)
    if n < 1 or 12 + n > len(d):
        raise ValueError("bad frame_id length %d" % n)
    frame_id = bytes(d[12:12 + n - 1]).decode()
    o = (12 + n + 7) & ~7
    if o + 8 + 8 + 4 > len(d):
        raise ValueError("truncated before the point array")
    timebase, = struct.unpack_from("<Q", d, o)
    o += 8
    point_num, lidar_id = struct.unpack_from("<IB", d, o)
    o += 8
    count, = struct.unpack_from("<I", d, o)
    o += 4
    if len(d) - o < max(count * _STRIDE - 1, 0):
        raise ValueError("truncated: %d points need %d bytes, %d left" % (count, count * _STRIDE - 1, len(d) - o))
    return {"sec": sec, "nanosec": nsec, "frame_id": frame_id, "timebase": timebase, "point_num": point_num, "lidar_id": lidar_id}, o, count, d


def decode_custom_msg(data):
    """Pure-stdlib reference decoder. Points are (offset_time, x, y, z, reflectivity, tag, line) tuples."""
    msg, o, count, d = _header(data)
    msg["points"] = [struct.unpack_from("<IfffBBB", d, o + i * _STRIDE) for i in range(count)]
    return msg


def cloud_bytes(points):
    """x y z intensity float32 per point, dropping any point with a non-finite coordinate."""
    out = bytearray()
    for _, x, y, z, refl, _, _ in points:
        if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
            out += struct.pack("<ffff", x, y, z, float(refl))
    return bytes(out)


def decode_custom_msg_numpy(data):
    """Fast decoder. msg["array"] is a structured array with fields t x y z refl tag line."""
    import numpy as np
    msg, o, count, d = _header(data)
    dtype = np.dtype({"names": ["t", "x", "y", "z", "refl", "tag", "line"],
                      "formats": ["<u4", "<f4", "<f4", "<f4", "u1", "u1", "u1"],
                      "offsets": [0, 4, 8, 12, 16, 17, 18], "itemsize": _STRIDE})
    if count == 0:
        msg["array"] = np.empty(0, dtype)
    else:
        buf = bytes(d[o:o + count * _STRIDE - 1]) + b"\0"  # the last point has no pad byte
        msg["array"] = np.frombuffer(buf, dtype, count=count)
    return msg


def cloud_bytes_numpy(array):
    import numpy as np
    out = np.empty((len(array), 4), "<f4")
    out[:, 0], out[:, 1], out[:, 2], out[:, 3] = array["x"], array["y"], array["z"], array["refl"]
    return out[np.isfinite(out[:, :3]).all(axis=1)].tobytes()


def main():
    """ROS node. Imports stay inside so the L0 tests need no ROS."""
    import rclpy
    from livox_ros_driver2.msg import CustomMsg
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import PointCloud2, PointField

    class Converter(Node):
        def __init__(self):
            super().__init__("livox_custom_to_cloud")
            self.declare_parameter("input_topic", "/livox/lidar")
            self.declare_parameter("output_topic", "/cloud_relay")
            try:
                import numpy  # noqa: F401
                self._fast = True
            except ImportError:
                self._fast = False
                self.get_logger().warning("numpy not found: using the slow decoder, which cannot keep up with 10 Hz")
            qos = lambda rel: QoSProfile(reliability=rel, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)
            self._pub = self.create_publisher(PointCloud2, self.get_parameter("output_topic").value, qos(ReliabilityPolicy.BEST_EFFORT))
            self.create_subscription(CustomMsg, self.get_parameter("input_topic").value, self._on_raw, qos(ReliabilityPolicy.RELIABLE), raw=True)
            self._count = 0
            self._fields = [PointField(name=n, offset=off, datatype=PointField.FLOAT32, count=1) for n, off in FIELDS]
            self.get_logger().info("CustomMsg %s -> PointCloud2 %s (%s decoder)" % (
                self.get_parameter("input_topic").value, self.get_parameter("output_topic").value, "numpy" if self._fast else "stdlib"))

        def _on_raw(self, data):
            try:
                if self._fast:
                    msg = decode_custom_msg_numpy(data)
                    payload = cloud_bytes_numpy(msg["array"])
                else:
                    msg = decode_custom_msg(data)
                    payload = cloud_bytes(msg["points"])
            except ValueError as err:
                self.get_logger().error("dropping an undecodable CustomMsg: %s" % err)
                return
            out = PointCloud2()
            out.header.stamp.sec, out.header.stamp.nanosec, out.header.frame_id = msg["sec"], msg["nanosec"], msg["frame_id"]
            out.height, out.width = 1, len(payload) // POINT_STEP
            out.fields, out.is_bigendian, out.point_step = self._fields, False, POINT_STEP
            out.row_step, out.data, out.is_dense = len(payload), payload, True
            self._pub.publish(out)
            self._count += 1
            if self._count == 1:
                self.get_logger().info("first cloud: %d points, frame %s" % (out.width, out.header.frame_id))

    rclpy.init()
    node = Converter()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
