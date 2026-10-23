"""T3.5e A1: save the first colour frame of each bag (and one at +3 s) so the two starting views can be compared by eye.
usage: reloc_first_frames.py OUTDIR BAG [BAG ...]   (bags in order; files named f<i>_first.png / f<i>_3s.png)"""
import os, sys
import cv2, numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

TOPIC = '/camera/camera/color/image_raw'


def frames(bag):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=[TOPIC]))
    t0 = None
    while r.has_next():
        _, data, _ = r.read_next()
        m = deserialize_message(data, get_message(types[TOPIC]))
        s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        t0 = s if t0 is None else t0
        a = np.frombuffer(m.data, np.uint8).reshape(m.height, m.step)[:, :m.width * 3].reshape(m.height, m.width, 3)
        yield s - t0, (a[:, :, ::-1] if m.encoding == 'rgb8' else a), m.encoding


if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for i, bag in enumerate(sys.argv[2:]):
        got3 = False
        for dt, img, enc in frames(bag):
            if dt == 0 or not os.path.exists('%s/f%d_first.png' % (out, i)):
                cv2.imwrite('%s/f%d_first.png' % (out, i), img); print(bag, 'first frame', img.shape, enc)
            if dt >= 3.0:
                cv2.imwrite('%s/f%d_3s.png' % (out, i), img); print('frame at +%.2f s' % dt); break
