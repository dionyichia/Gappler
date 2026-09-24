# ARM Bring-Up: Driver Handshake and Joint Feedback (Draft)

> **UNVALIDATED.** This shared runbook is a draft for T1.6's first powered arm session. Sherman
> and Dion must review it together **before** its attended trial at the robot. It is not yet an
> independently verified operating procedure. T1.5 and T1.6 remain open in
> [`task-tree.html`](task-tree.html); incorporate the T1.6 observations before treating it as
> validated or marking T1.5 done.

## Goal and boundary

Ready means **one RM65 driver completed its controller handshake, UDP packets from the arm are
arriving at the configured host port, and ROS `/joint_states` carries plausible, continuing
six-joint messages during the packet observation**. No arm motion is commanded. This does not
verify MoveIt, the wrist camera, the gripper, a home pose, or a grasp.

**Why packets are a separate gate:** the vendor UDP callback stores joint readings, but a timer
publishes those stored positions with a *new* timestamp on every tick
(`arm/vendor/rm_driver/src/rm_driver.cpp:3604-3615,3768-3807`). Advancing ROS timestamps and a
good `ros2 topic hz` rate alone do not prove fresh arm data. A stationary arm need not change
joint positions, so changing angles are not a requirement for this no-motion test either.

The checks below must be performed by people at the robot, not by automation. `grasp_state_machine`,
`launchers/start_grasp_pipeline.py`, `launchers/grasp_orchestrator.py`, and root `main.py` are
**not** part of this procedure: the state machine homes the arm unprompted
(`ORIENTATION.md` §8.1; repository `CLAUDE.md` §Safety). The full
`arm/arm_bringup/launch/arm_bringup.launch.py` also starts `rm_control` and MoveIt as well as the
driver (`arm/arm_bringup/launch/arm_bringup.launch.py:18-60`), so use the driver-only launch below.
Neither Ctrl+C in a launch terminal nor the spoken word "stop" is an arm emergency stop
(`sherman_docs/T1.2_SAFETY_FIXES.md` §B1; `CODE_AUDIT.md` §B3).

## Before controller power

1. **Physical setup, led by Sherman.** `[reported]` T1.4 was marked DONE on 2026-09-23 for
   *power-on with no motion* ([`task-tree.html`](task-tree.html), T1.4;
   `sherman_docs/T1.4_PHYSICAL_SETUP.md:235-272`). Read its accepted visit record rather than
   reopening its measurements: the 0.03 m rear overhang is recorded, D1 area figures were waived,
   and the physical-stop reach was confirmed verbally with its D3 number still owed. There is no
   fenced zone or table/cell. Before **this** session, confirm the arm remains in its as-found
   posture, the area and mount/cables have not changed, and an identified **physical** controller
   stop is within reach of the operator's actual standing position (not just the `estop.py`
   terminal). Do not force braked joints into position. If current conditions have changed or the
   physical stop is not reachable, stop and reassess; the waived D3 number is not itself a new
   T1.6 power-on gate. The table/cell and arm sweep remain out of scope until T1.3/T1.7 motion work.
2. **Roles and shared equipment.** Name the computer operator and a *different* person at the
   physical stop; both must remain present. The stop operator stays with the physical stop while
   the computer operator handles terminals. Record the controller's as-found power state. If it
   is already on without an agreed operator, stop and establish ownership first; do not cycle
   somebody else's controller. On the shared box, check who is using the arm. Never stop someone
   else's process. Read-only shared-hardware checks (`CLAUDE.md` §Safety):

   ```bash
   ps -eo pid,user,etime,args | grep -iE 'rm_driver|arm_bringup|grasp_state_machine|start_grasp_pipeline|grasp_orchestrator|realsense|rs_launch|ros2 launch|Runner.Worker|bench/run.sh'
   nvidia-smi
   fuser /dev/video*
   ```

   Expect no competing arm or shared-hardware session. The `grep` process itself may appear.
   If someone else is using shared hardware or process ownership is unclear, stop and coordinate
   before proceeding; do not terminate anything. Check the lab-box checkout **before power-on**:

   ```bash
   git -C ~/rcp-Gappler status --short --branch
   git -C ~/rcp-Gappler rev-parse --short HEAD
   ```

   Expect the agreed T1.6 code revision and a clean worktree (ignored build output is normal).
   The arm overlay must be built from that approved revision, not a copied older checkout. If the
   branch, revision, build provenance, or local changes are unresolved, mark this session
   **INCOMPLETE** and coordinate with the checkout owner. Do not stash, discard, switch branches,
   pull, or rebuild over someone else's work. Also check that passive network capture is available;
   without it this procedure cannot establish READY:

   ```bash
   command -v tcpdump
   sudo -v
   ```

   Expect a path to `tcpdump` and a successful sudo authentication for the computer operator.
   `sudo -v` checks access but starts no capture. If either is missing, postpone this test and
   arrange a permitted read-only packet observer.
   Do not install tools or change host configuration during the first-power session.
3. **Private ROS channel.** Use fresh terminals on `~/rcp-Gappler`: one for the software stop
   (T-ESTOP), driver (T-DRIVER), ROS inspection (T-INSPECT), and passive packet observation
   (T-NET). Do not layer over a previously sourced ROS workspace. In each *ROS* terminal,
   source this checkout's arm overlay and set the same unused ROS domain. `91` is a proposed
   domain **only if it is empty**. Run this setup in T-ESTOP, T-DRIVER and T-INSPECT **before**
   starting the stop program:

   ```bash
   source ~/rcp-Gappler/arm/arm_env.sh
   export ROS_DOMAIN_ID=91
   export ROS_LOCALHOST_ONLY=1
   ros2 node list
   ```

   Expect no nodes before the stop program starts. If `arm_env.sh` reports missing `install/`, or
   if nodes are present, stop and resolve that before power-on. Choose another empty domain rather
   than sharing traffic with another operator. `arm_env.sh` sources ROS 2 Humble and the arm overlay
   (`arm/arm_env.sh:5-11`). In T-INSPECT, also run `ros2 pkg prefix rm_driver` and confirm the
   returned prefix is inside `~/rcp-Gappler/install/`; this locates the package but does not prove
   when its binary was built. The stop program, driver, and inspection terminal **must** agree on
   domain and localhost setting. T-NET observes the physical wired interface directly; ROS
   domain settings do not filter the arm's TCP and UDP traffic.
4. **Software stop ready, physical stop primary.** The computer operator starts T-ESTOP in a
   separate, attended terminal after step 3:

   ```bash
   python3 ~/rcp-Gappler/arm/estop/estop.py
   ```

   Expect `E-stop ready` and an open terminal. `E` sends a ROS emergency-stop command **only when
   T-ESTOP has focus**; switching to T-DRIVER, T-NET, or T-INSPECT removes that focus. The physical
   stop operator remains ready throughout. Ctrl+C *in T-ESTOP* sends a stop and exits. `Q` exits
   without a stop; `R` sends resume and must not be used as a setup check
   (`arm/estop/estop.py:3-13,32-55,94-125`). Before the driver subscribes, a ROS stop message may
   have no recipient; the physical stop remains the immediate fallback. The code waits for DDS
   acknowledgement but **does not check its return value** (`arm/estop/estop.py:57-61,119-125`):
   an exit or `EMERGENCY STOP SENT` log does not prove delivery or physical stopping. If T-ESTOP
   exits unexpectedly or the physical stop operator is not ready, end the procedure.

## Controller, driver, and feedback

5. **Network and controller, computer operator and person at the robot.** Confirm the workstation's
   wired NIC `enp2s0` has `192.168.1.10/24` as well as the saved `.100` and `.5` addresses
   (`sherman_docs/T0.2_SESSION.md:26-34,73-99`). The driver expects the controller at `.18:8080`
   and sends UDP feedback to `.10:8089` (`arm/vendor/rm_driver/config/rm_65_config.yaml:4-12`). Do not
   run the old base startup scripts: they remove `.10` (`sherman_docs/T0.2_SESSION.md:116-119`).

   ```bash
   ip -4 addr show enp2s0
   ```

   Expect a link with carrier and `.10/24`; stop if either is missing. Record discrepancies in
   `.100` or `.5` for the network owner, but those addresses are not the arm-feedback path. The
   person at the robot then powers the controller; record the power-on time. After power-on, check
   reachability and its
   control port:

   ```bash
   ping -I 192.168.1.10 -c 3 192.168.1.18
   nc -zv -w 3 192.168.1.18 8080
   ```

   Expect ping replies and a successful connection. `[reported]` The archived 2026-08-25 guide
   says port 8080 can take about 60 seconds after power-on
   (`archive/RCP_NEW_USER_STARTUP_GUIDE.md` §3.3). A refusal immediately after power-on merits
   waiting and retrying; record how long it actually takes. If the port remains unavailable
   after the session's agreed boot window, **do not start the driver**. A timeout or unreachable
   host also requires checking power, cable, and addressing.
6. **Passive packet observation, computer operator.** Before launching the driver, open T-NET on
   the lab box and start a capture filtered to UDP from controller `.18` to host `.10:8089`:

   ```bash
   sudo tcpdump -n -i enp2s0 'udp and src host 192.168.1.18 and dst host 192.168.1.10 and dst port 8089'
   ```

   This prints packet headers without sending anything to the arm or saving payloads. It remains
   open while steps 7 and 8 run. If it cannot start, stop before launching the driver. A configured
   UDP destination or an open socket is **not** evidence of received packets. After observing ROS
   feedback, return to T-NET, press Ctrl+C, and preserve the output including source, destination,
   port, packet count, and observation interval. Do not leave the capture running.
7. **Driver only, launched once by the computer operator.** In T-DRIVER with the same
   environment from step 3, run only:

   ```bash
   ros2 launch rm_driver rm_65_driver.launch.py
   ```

   Keep this terminal open and record its output. `[code]` The driver logs
   `product_version = ...` after querying the controller, and a successful UDP setup logs
   `UDP_Configuration is cycle:5ms,port:8089,...,ip:192.168.1.10,...`
   (`arm/vendor/rm_driver/src/rm_driver.cpp:778-815,818-838`). `[reported]` The older checkout
   reported `product_version = RM65-BI` (`archive/RCP_NEW_USER_STARTUP_GUIDE.md` §4 T2).
   **Both expected lines need confirmation on this checkout during T1.6.** If the driver exits,
   reports an error, or the identity/configuration differs, end the attempt and preserve the logs.
   Before inspecting feedback, check in T-INSPECT that the software stop publishes and the driver
   subscribes on the same ROS topic:

   ```bash
   ros2 topic info -v /rm_driver/emergency_stop_cmd
   ```

   Expect one publisher (`estop`) and one subscriber (`rm_driver`). If either is absent, end the
   session: software `E` cannot be relied on. This check does not test the physical stop.
8. **ROS feedback and packet arrival, T-INSPECT and T-NET.** While the filtered capture runs,
   inspect the arm's ROS feedback in T-INSPECT:

   ```bash
   ros2 topic echo /joint_states --once
   ros2 topic hz -w 10 /joint_states
   ```

   Expect exactly `joint1` through `joint6`, six finite positions, and continuing messages
   **while a stream of packets from `.18` to `.10:8089` is independently observed**. One packet
   at startup is not enough: packet timestamps must span the ROS observation window. Record
   the measured ROS rate and how long both channels were watched. End the rate display with Ctrl+C in
   T-INSPECT, then Ctrl+C in T-NET to show its packet count. The driver config declares six joints
   (`arm/vendor/rm_driver/config/rm_65_config.yaml:7-8,25`); the bench treats an advertised but
   silent topic as failure (`bench/preflight.py:790-799`). A fresh ROS timestamp alone is **not**
   proof of fresh arm data; stationary joint positions may legitimately stay constant. There is
   no verified minimum rate: record the observed rate and packet count, not an invented threshold.
   Compare readings with the as-found posture; investigate non-finite, out-of-model or obviously
   implausible readings without calling this a home-pose calibration (T1.3/T1.7). If ROS messages
   are absent, or the packet stream does not persist, the session is **not READY**. Check `.10`,
   driver logs and competing processes, then end the attempt without trying motion. This proves
   the configured arm-to-host packet path and plausible ROS output during the same interval; it
   does not verify every packet was decoded or that joint calibration is correct.

## Stop conditions, shutdown, and verdict

- **Unexpected motion or uncertain arm state:** the person at the robot uses the agreed physical
  stop immediately. End the session, keep the evidence, and do not proceed to another step.
- **Ordinary failure or completed check:** the computer operator stops this session's packet
  capture in T-NET (if still running), then stops *this session's* driver in T-DRIVER and confirms
  both exited. The physical-stop operator powers the controller **off** and records that state.
  Only then close T-ESTOP. After the driver exits, the software stop no longer has an arm
  subscriber. If a named operator explicitly takes custody of a still-powered controller,
  record the handoff and remaining stop capability instead; never silently leave it powered.
  Do not use a broad `pkill` or stop somebody else's process. Ctrl+C in T-DRIVER is driver
  teardown, not an arm stop.
- **PASS T1.6:** correct handshake, independently observed arm packets continuing to arrive at
  `.10:8089` **during** plausible six-joint ROS feedback, and no motion commanded or observed.
  **INCOMPLETE:** prerequisites, packet-capture capability, or access unavailable. **FAIL:**
  wrong/missing handshake, no continuing arm packet stream, absent/implausible ROS feedback, or
  unexpected motion.
  A successful ping, an open TCP port, or an advertised topic alone is not a pass.

`./bench/run.sh robot` is a supplemental read-only L5 inventory, **not** this acceptance test:
it also checks the LiDAR, glasses, and wrist camera (`bench/preflight.py:908-929`).

### Failure branches

| Observation | Action and verdict |
|---|---|
| Area, rear overhang, mount/cables or physical-stop reach differ from the accepted T1.4 record | Do not power on. INCOMPLETE until the current setup is checked; T1.4's recorded 0.03 m overhang and D3 number owed were already accepted for no-motion power-on. |
| Lab-box checkout is modified, on an unapproved branch, or the arm overlay's build revision is unknown | Do not start the controller. INCOMPLETE; coordinate with its owner rather than switching, cleaning or rebuilding their checkout. |
| `enp2s0` has `NO-CARRIER` or no `.10/24` | Do not power on. Check switch/cabling or the approved NetworkManager profile, then reassess. |
| Ping works but port 8080 refuses immediately after power-on | Wait only within the agreed boot window, then retry and record elapsed time; unresolved means no driver launch. |
| T-NET cannot start or lacks capture permission | Do not launch the driver. INCOMPLETE; arrange a permitted read-only packet observer. |
| Driver handshake, model, or UDP setup differs | Stop this session's driver, preserve its log. FAIL; do not try the full grasp launcher. |
| Stop topic has no `estop` publisher or `rm_driver` subscriber | Stop; the software stop path is not connected. FAIL even if the physical stop is present. |
| ROS `/joint_states` appears but T-NET sees no continuing `.18` → `.10:8089` traffic | FAIL: timer-produced ROS messages may contain cached readings. Do not infer live feedback from their timestamps. |
| T-NET sees packets but ROS joint messages are absent, malformed, or implausible | FAIL: receipt on the NIC does not establish the driver decoded and published valid joints. |
| Any unrequested motion | Physical-stop operator uses the controller stop immediately. FAIL; record the event and end the session. |

## Evidence to collect during T1.6

Record date/time, people and roles, T1.4 sign-off and any remaining overhang or stop-reach issues,
as-found posture and power state, physical-stop position, ROS domain, approved checkout commit and
arm overlay build provenance, NIC
addresses, source-addressed ping, time to open port, driver handshake and UDP setup log lines,
software-stop publisher/subscriber counts, **filtered tcpdump output and packet count with a time
interval overlapping the ROS observation**, joint names/positions/timestamps, measured ROS rate
and watch duration, any movement, failure symptoms, and final process/controller power states.
Label values from code `[code]`, the archived guide `[reported]`, and T1.6 results `[observed]`.
Record a T4.3 defect-log entry for surprises. Revise this draft from those results before marking
T1.5 done or treating it as an independently validated shared runbook.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-23 | OpenCode + Sherman | Drafted the T1.6 no-motion, driver-only handshake and joint-feedback procedure. Hardware outputs remain unverified. |
| 2026-09-23 | OpenCode + Sherman | Moved the shared draft to docs/; required independent UDP receipt, clarified stop-terminal roles and first-power shutdown. Still unvalidated. |
| 2026-09-23 | OpenCode + Sherman | After merging current dev, replaced the stale open-T1.4 blocker with its accepted no-motion verdict, documented rear overhang and D3 residual, and a day-of-condition check. No hardware run. |
| 2026-09-23 | OpenCode + Sherman | Added a checkout/overlay provenance gate after a read-only lab-box check found an older branch with local changes; do not change that checkout during first-power verification. |
