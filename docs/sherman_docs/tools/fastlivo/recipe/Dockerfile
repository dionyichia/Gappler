# Optional uncapped build route; prefer bash run_build.sh for hard cgroup limits.
FROM ros:humble-perception-jammy
COPY build_inside.sh patch_cmake.py patch_vio.py patch_sampling.h /opt/recipe/
RUN bash /opt/recipe/build_inside.sh
WORKDIR /fast_livo_ws
USER user
ENTRYPOINT []
CMD ["bash"]
