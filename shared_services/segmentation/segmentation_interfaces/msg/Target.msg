# What the grasp client should look for. Sent by the aria client on /grasp/target.

std_msgs/Header    header           # stamp of the glasses frame the target came from
string             prompt           # object words. Empty = stop and clear
sensor_msgs/Image  reference        # OPTIONAL crop of the chosen object. width 0 = none
sensor_msgs/Image  reference_mask   # OPTIONAL mono8 mask, same size as reference
