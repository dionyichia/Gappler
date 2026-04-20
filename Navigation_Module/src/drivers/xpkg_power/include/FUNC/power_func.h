#ifndef POWER_FUNC_H
#define POWER_FUNC_H

#include <unistd.h>
#include <string>
#include <vector>
#include <lib_file_ini.h>
#include <ArduinoJson.h>
#include <ros_interface.h>

using namespace std;
using namespace XROS_POWER;
////////////////////////////info of vehicle//////////////////////////////////////
#define MODE_AUTO 0
#define MODE_MANUAL 1

#define MANUAL_OFF 0
#define MANUAL_ON 1

struct PowerInfo
{
    //vehicle info
    unsigned char s_type = 0;
    unsigned char s_num = 0;
    //hardware and software version
    std::string s_ver_hard = "--";
    std::string s_ver_soft = "--";
    //system status
    bool s_en_state = false;

    char BMS_work_state = 0;    //0x00: ok / 0x01: warning /  0x02: protect
    bool BMS_charge_state = 0;  //0x00: off / 0x01: on

    bool BMS_warning_state = 0;
    bool BMS_warning_over_vol = false;
    bool BMS_warning_low_vol = false;
    bool BMS_warning_over_heat = false;
    bool BMS_warning_low_heat = false;
    bool BMS_warning_over_discharge = false;
    bool BMS_warning_over_charge = false;
    bool BMS_warning_low_battery = false;
    bool BMS_protect_state = 0;
    bool BMS_protect_over_vol = false;
    bool BMS_protect_low_vol = false;
    bool BMS_protect_over_heat = false;
    bool BMS_protect_low_heat = false;
    bool BMS_protect_over_discharge = false;
    bool BMS_protect_over_charge = false;
    bool BMS_protect_low_battery = false;
    bool BMS_protect_short = false;

    char BMS_SOC = 0;
    char BMS_SOH = 0;
    float BMS_vol = 0;
    float BMS_cur = 0;
    float BMS_heat = 0;

    char charger_work_state = 0; //0:disconnect/ 1:connect / 2:full / 3:error
    char charger_work_mode = 0;  //0:auto / 1:manual
    char charger_touch_state = false;//0:untouch / 1:touch
    char charger_beep_state = false;
    float charger_rec_vol = 0;
    float charger_min_cur = 0;

    char charger_error_state = 0;//0:none/ 1:over vol/ 2:over current/ 3:short circuit

    float charger_vol = 0;
    float charger_cur = 0;

};
//////////////////////////////////////////////////////////////////
class PowerFunc
{
public:
    explicit PowerFunc(void);
    static PowerFunc& GetPowerFunc();
    inline PowerInfo GetPowerInfo(void){ return m_dev_info; }
    inline int IsOnline(void){ return f_online; }
    inline int IsReady(void){ return f_ready; }
    inline int IsEnable(void){ return f_enable; }
    void BaseInit(void);
    void OnlineCheck(void);
    void EnableCheck(void);

    void ComDataIn(void);
    void CtrlDataIn(void);
    void VelOut(void);
    void DevInfoOut(void);

    void DevReset(void);
    void DevClear(void);
    void DevVersion(void);
    void DevSetEnable(bool en);
    void ChargeSetState(unsigned char mode,unsigned char manual,bool beep,float vol,float cur);

public:
    std::string m_data_json;

private:
    PowerInfo m_dev_info;
    bool f_online;
    bool f_enable;
    bool f_ready;
    int m_online_count;
};

#endif // POWER_FUNC_H
