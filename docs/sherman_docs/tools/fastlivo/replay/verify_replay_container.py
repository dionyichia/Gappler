"""Fail-closed validation of the exact stopped offline replay container."""
import json
import sys

COMMAND = "source /opt/ros/humble/setup.bash && source /fast_livo_ws/install/setup.bash && exec python3 /tmp/t59/replay.py"
ENV = {
    "ROS_DOMAIN_ID": "173", "ROS_LOCALHOST_ONLY": "1",
    "ROS2CLI_NO_DAEMON": "1", "HOME": "/tmp/t59",
    "ROS_HOME": "/tmp/t59/ros", "ROS_LOG_DIR": "/tmp/t59/ros-log",
    "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def validate(doc: dict, image_id: str, image_tag: str = "t59-fast-livo2:experimental") -> None:
    """Reject missing or unsafe inspection fields before any process starts."""
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    require(doc["Image"] == image_id, "image ID changed")
    require(doc["State"]["Status"] == "created" and not doc["State"]["Running"],
            "container is not newly created/stopped")
    require(doc["Mounts"] == [], "mounts forbidden")
    require(set(doc["NetworkSettings"]["Networks"]) == {"none"}, "additional networks forbidden")
    cfg, host = doc["Config"], doc["HostConfig"]
    for key, expected in {
        "Image": image_tag, "User": "10001:10001",
        "WorkingDir": "/fast_livo_ws", "Entrypoint": ["/bin/bash"],
        "Cmd": ["-c", COMMAND],
    }.items():
        require(cfg[key] == expected, "unexpected Config." + key)
    env = dict(item.split("=", 1) for item in cfg["Env"])
    require(all(env.get(k) == v for k, v in ENV.items()), "unsafe ROS/runtime environment")
    for key, expected in {
        "NetworkMode": "none", "Privileged": False, "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges:true"],
        "Memory": 8 * 1024**3, "MemorySwap": 8 * 1024**3,
        "NanoCpus": 2000000000, "PidsLimit": 512,
        "PublishAllPorts": False, "PidMode": "", "IpcMode": "private",
        "ReadonlyRootfs": False,
        "AutoRemove": False, "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
    }.items():
        require(host[key] == expected, "unsafe HostConfig." + key)
    for key in ("CapAdd", "Binds", "Devices", "DeviceRequests", "PortBindings"):
        require(key in host and not host[key], "forbidden HostConfig." + key)
    for key in ("VolumesFrom", "Links", "ExtraHosts", "DeviceCgroupRules", "Tmpfs"):
        require(not host.get(key), "forbidden HostConfig." + key)
    require(not cfg.get("Volumes"), "image-declared volumes forbidden")


if __name__ == "__main__":
    try:
        with open(sys.argv[1], encoding="utf-8") as source:
            docs = json.load(source)
        if len(docs) != 1:
            raise ValueError("expected exactly one container")
        validate(docs[0], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "t59-fast-livo2:experimental")
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        sys.exit("REFUSED: " + str(error))
    print("Stopped container isolation verified; this is not runtime acceptance.")
