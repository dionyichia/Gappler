//////////////////////////////////////////////////
//xnode for power control V2.0
//xpkg_power
//////////////////////////////////////////////////
#include <ros_interface.h>
#include <power_func.h>
#include <lib_file_ini.h>

#define SYS_BASE_INIT 0
#define SYS_READY 1

using namespace XROS_POWER;

void TimeCallback() {
    PowerFunc& power_func = PowerFunc::GetPowerFunc();
    static char sys_state = SYS_BASE_INIT;

    power_func.ComDataIn();
    power_func.OnlineCheck();
    power_func.EnableCheck();

    switch(sys_state)
    {
    case SYS_BASE_INIT:
        power_func.BaseInit();
        if(power_func.IsReady())sys_state = SYS_READY;
        break;
    case SYS_READY:
        power_func.CtrlDataIn();
        power_func.VelOut();
        power_func.DevInfoOut();
        if(!power_func.IsOnline())sys_state = SYS_BASE_INIT;
        break;
    }
}
/*------------------------------------------------------------------------------------------------------------------
 * name: main
 -----------------------------------------------------------------------------------------------------------------*/
int main(int argc, char **argv)
{
    //system("gnome-terminal -x bash -c 'source /opt/ros/melodic/setup.bash;roscore'&");
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    ros_interface.BaseInit(argc, argv, "xnode_power", 100.0, TimeCallback);
    while(ros_interface.NodeCheck("xnode_comm") == false)
    {
        usleep(1000000);
        ros_interface.ROSLog(LogLevel::kError," Please bringup node<xnode_comm> first!!!!!!!!!!!!!!!!!!!");
            //ros_interface.Shutdown();
    }

    LibFileIni& lib_file_ini = LibFileIni::GetLibFileIni();
    lib_file_ini.OpenFile(ros_interface.m_ini_path.c_str());

    ros_interface.Work();
    ros_interface.BaseDeinit();
    return 0;
}
