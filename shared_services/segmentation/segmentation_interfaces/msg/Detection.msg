# One object the segmentation service found in the request image.

sensor_msgs/Image             mask        # mono8, same size as the image, 1 = object, 0 = not
float32                       score       # SAM 3 confidence, 0 to 1
sensor_msgs/RegionOfInterest  bbox        # pixel box around the mask
uint32                        area_px     # mask pixel count
float32                       u           # centroid pixel column
float32                       v           # centroid pixel row
float32                       depth_m     # median valid depth under the mask. NaN if no depth was
                                          #   sent or no pixel under the mask had a reading
bool                          has_point   # true only if depth and camera_info were sent and
                                          #   depth_m is valid
geometry_msgs/Point           point       # metres, in the reply header's frame_id (the camera's
                                          #   optical frame): x right, y down, z out of the lens
