# Subscribe to every stream type on an already-running Aria stream and count what arrives in 10 s.
# Start the stream first: aria streaming start --interface usb --profile profile18 --use-ephemeral-certs
import time, collections, aria.sdk as aria
aria.set_log_level(aria.Level.Error)
c = aria.StreamingClient(); cfg = c.subscription_config
types = [t for n, t in vars(aria.StreamingDataType).items() if isinstance(t, aria.StreamingDataType) and n not in ("Unknown",)]
mask = types[0]
for t in types[1:]: mask = mask | t
print("subscribing to", [str(t) for t in types])
cfg.subscriber_data_type = mask
cfg.security_options.use_ephemeral_certs = True
c.subscription_config = cfg
n = collections.Counter()
class Obs:
    def on_image_received(self, img, rec): n["image_" + str(rec.camera_id)] += 1
    def on_audio_received(self, data, rec): n["audio"] += 1
    def on_imu_received(self, samples, idx): n[f"imu{idx}"] += 1
    def on_magneto_received(self, s): n["magneto"] += 1
    def on_baro_received(self, s): n["baro"] += 1
    def on_streaming_client_failure(self, reason, msg): print("FAILURE", reason, msg); n["failure"] += 1
c.set_streaming_client_observer(Obs()); c.subscribe(); time.sleep(10); c.unsubscribe()
print("received in 10 s:", dict(n))
