## ROS driver for power

How to use xpkg_XXX(XXX is your device) ros driver
=====================================================================
        1) Clone this ros package folder(xpkg_XXX) to your catkin's workspace src folder
        2) Run catkin_make to build
        3) Add path of setup.bash to ~/.bashrc like: echo "source ~/workspace/devel/setup.bash">> ~/.bashrc	source ~/.bashrc
        4) Change parameters in xnode_XXX_test.launch(xpkg_XXX/launch/xnode_XXX_test.launch)
        6) prepare xpkg_comm and Roslaunch xnode_comm.launch(xpkg_comm/launch/xnode_comm.launch)
        7) Roslaunch xnode_XXX_test.launch(xpkg_XXX/launch/xnode_XXX_test.launch)
        8) Use topic /xpkg_XXX/ctrl_json to control sensor function

Note
=====================================================================
        1) When device connect successfully,ros will print out:"xnode_XXX: device online"
        2) When device enable successfully,ros will print out:"xnode_XXX: device enable"
        3) When device ready,ros will print out:"xnode_XXX: device init finish"
        4) Don't Change parameter of "ini_path"
        5) This node will publish message "/xtopic_XXX/device_state_json" and "/xtopic_comm/com_send_xstd"
        6) Must run with xpkg_comm

Special note: please use include/LIB_JSON/ArduinoJson.h,view < https://arduinojson.org > for details


Parameter
=====================================================================
        1) (bool) test_mode :                   (true/false)Will publish cmd_vel.Used for auto charger test
        2) (bool) manu_enable :                 (true/false)Enable manu mode
        3) (bool) manu_state :                  (true/false)on/off of charger in manu mode
        4) (bool) beep_enable :                 (true/false)Enable beep
        5) (double) rec_voltage :               (0.1~25.5)The voltage fall before recharge
        6) (double) min_current :               (0.1~10)Minimum current when turn off charger
        7) ini_path :                           DON'T CHANGE

json out list(/xtopic_power/device_state_json)
=====================================================================
        1) (char) BMS_work_state :              0=ok 1=warring 2=protect
        2) (bool) BMS_charge_state :            0=uncharge 1=charging
        3) (bool) BMS_warning_state :           Check BMS warning list
        4) (bool) BMS_protect_state :           Check BMS protect list
        5) (char) BMS_SOC :                     SOC of battery
        6) (char) BMS_SOH :                     SOH of battery
        7) (float) BMS_voltage :                (unit: V) Voltage of battery
        8) (float) BMS_current :                (unit: A) Current of battery
        9) (float) BMS_heat :                   (unit: °c) Temperature of battery

        10) (char) charger_work_state :         0=disconnect 1=connect 2=full 3=error
        11) (char) charger_work_mode :          0=auto 1=manu
        12) (char) charger_touch_state :        0=untouch 1=touch
        13) (char) charger_error_state :        Check charger error list
        14) (char) charger_beep_state :         0=off 1=on
        15) (float) charger_rec_voltage :       (unit: V) The voltage fall before recharge
        16) (float) charger_min_current :       (unit: A) Minimum current when turn off charger
        17) (float) charger_voltage :           (unit: V) Voltage of charge
        18) (float) charger_current :           (unit: A) Current of charge

json in list(/xtopic_power/ctrl_json)
=====================================================================
        1) (bool) manu_enable :                 (true/false) Enable manu mode
        2) (bool) manu_state :                  (true/false) on/off of charger in manu mode
        3) (bool) beep_enable :                 (true/false) Enable beep
