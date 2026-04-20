#include <power_func.h>
#include <string>
#include <vector>

#define DEV_NODE_NAME "xnode_power"
#define DEV_CLASS 0x06

PowerFunc::PowerFunc()
{
    f_online = false;
    f_enable = false;
    f_ready = false;
    m_online_count = 200;
}
/*------------------------------------------------------------------------------------------------------------------
 * name: GetPowerFunc
 -----------------------------------------------------------------------------------------------------------------*/
PowerFunc& PowerFunc::GetPowerFunc()
{
    static PowerFunc power_func;
    return power_func;
}
/*------------------------------------------------------------------------------------------------------------------
 * name: BaseInit
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::BaseInit(void)
{
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    LibFileIni& lib_file_ini = LibFileIni::GetLibFileIni();
    f_ready = false;   
    if(m_dev_info.charger_min_cur != 0.0 && m_dev_info.charger_rec_vol != 0.0)
    {
        ChargeSetState(ros_interface.m_manu_enable,ros_interface.m_manu_state,ros_interface.m_beep_enable,ros_interface.m_rec_voltage,ros_interface.m_min_current);

    };
    if(f_online && f_enable)
    {
        ros_interface.ROSLog(LogLevel::kInfo,"\033[1;34m %s: Device type = %s \033[0m",DEV_NODE_NAME,
                             lib_file_ini.GetKeyValue(lib_file_ini.ToHexStr(m_dev_info.s_type).c_str(),"type").c_str());
        ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: ### Device init finish ### \033[0m",DEV_NODE_NAME);
        //ros_interface.ROSLog(LogLevel::kInfo,"%d",ros_interface.m_beep_enable);
        f_ready = true;
    }
}
/*------------------------------------------------------------------------------------------------------------------
 * name: OnlineCheck
 -----------------------------------------------------------------------------------------------------------------*/
#define ONLINE_INIT 0
#define ONLINE 1
#define OFFINE 2
void PowerFunc::OnlineCheck()
{
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    static char online_state = ONLINE_INIT;
    if(m_online_count == 0)f_online = false;
    else m_online_count--;
    switch(online_state)
    {
    case ONLINE_INIT:
        if(m_online_count == 1)
        {
            ros_interface.ROSLog(LogLevel::kError," %s: Device offline,please check cable connection",DEV_NODE_NAME);
            online_state = OFFINE;
        }
        if(f_online)
        {
            ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: Device online \033[0m",DEV_NODE_NAME);
            online_state = ONLINE;
        }
        break;
    case OFFINE:
        if(f_online)
        {
            ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: Device online \033[0m",DEV_NODE_NAME);
            online_state = ONLINE;
        }
        break;
    case ONLINE:
        if(!f_online)
        {
            ros_interface.ROSLog(LogLevel::kError," %s: Device offline,please check cable connection",DEV_NODE_NAME);
            online_state = OFFINE;
        }
        break;
    }
}
/*------------------------------------------------------------------------------------------------------------------
 * name: EnableCheck
 -----------------------------------------------------------------------------------------------------------------*/
#define ENABLE_INIT 0
#define ENABLE_INIT_FINISH 1
#define ENABLE 2
#define DISABLE 3
#define SLEEP 6
void PowerFunc::EnableCheck()
{
    static int sleep_count = SLEEP;
    if(!f_online)return;
    if(sleep_count < SLEEP)
    {
        sleep_count++;
        return;
    }
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    static char enable_state = ENABLE_INIT;
    switch(enable_state)
    {
    case ENABLE_INIT:
        DevSetEnable(1);
        sleep_count = 0;
        enable_state = ENABLE_INIT_FINISH;
        break;
    case ENABLE_INIT_FINISH:
        if(m_dev_info.s_en_state)
        {
            ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: Device enable \033[0m",DEV_NODE_NAME);
            enable_state = ENABLE;
            f_enable = true;
        }
        else
        {
            ros_interface.ROSLog(LogLevel::kWarn," %s: Device disable",DEV_NODE_NAME);
            enable_state = DISABLE;
            f_enable = false;
        }
        break;
    case ENABLE:
        if(!m_dev_info.s_en_state)
        {
            ros_interface.ROSLog(LogLevel::kWarn," %s: Device disable",DEV_NODE_NAME);
            enable_state = DISABLE;
            f_enable = false;
        }
        break;
    case DISABLE:
        if(m_dev_info.s_en_state)
        {
            ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: Device enable \033[0m",DEV_NODE_NAME);
            enable_state = ENABLE;
            f_enable = true;
            break;
        }
        DevSetEnable(1);
        sleep_count = 0;
        break;
    }
}
/*------------------------------------------------------------------------------------------------------------------
 * name: VelOut
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::VelOut()
{
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    if(ros_interface.m_test_mode)
    {
        double speed;        
        static bool state_old = false;
        static int num = 0;
        if(!m_dev_info.charger_touch_state)speed=0.02;
        else speed=-0.015;
        ros_interface.PubVel(speed,0,0);
        if(state_old != m_dev_info.charger_touch_state)
        {
            state_old = m_dev_info.charger_touch_state;
            ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: charger_touch_state = %d \033[0m",DEV_NODE_NAME,m_dev_info.charger_touch_state);
            if(m_dev_info.charger_touch_state)ros_interface.ROSLog(LogLevel::kInfo,"\033[1;32m %s: test num:%d",DEV_NODE_NAME,num++);
        }
    }
}
/*------------------------------------------------------------------------------------------------------------------
 * name: DevInfoOut
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::DevInfoOut()
{
    if(f_online == 0)return;
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    std::string send_data;
    DynamicJsonDocument doc(1024);

    doc["BMS_work_state"] = m_dev_info.BMS_work_state;
    doc["BMS_charge_state"] = m_dev_info.BMS_charge_state;
    doc["BMS_warning_state"] = m_dev_info.BMS_warning_state;
    doc["BMS_protect_state"] = m_dev_info.BMS_protect_state;
    doc["BMS_SOC"] = m_dev_info.BMS_SOC;
    doc["BMS_SOH"] = m_dev_info.BMS_SOH;
    doc["BMS_voltage"] = m_dev_info.BMS_vol;
    doc["BMS_current"] = m_dev_info.BMS_cur;
    doc["BMS_heat"] = m_dev_info.BMS_heat;

    doc["charger_work_state"] = m_dev_info.charger_work_state;
    doc["charger_work_mode"] = m_dev_info.charger_work_mode;
    doc["charger_touch_state"] = m_dev_info.charger_touch_state;
    doc["charger_error_state"] = m_dev_info.charger_error_state;
    doc["charger_beep_state"] = m_dev_info.charger_beep_state;
    doc["charger_rec_voltage"] = m_dev_info.charger_rec_vol;
    doc["charger_min_current"] = m_dev_info.charger_min_cur;
    doc["charger_voltage"] = m_dev_info.charger_vol;
    doc["charger_current"] = m_dev_info.charger_cur;

    serializeJson(doc, send_data);
    ros_interface.PubDevState(send_data);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: CtrlDataIn
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::CtrlDataIn()
{
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    bool buff_manu_enable,buff_manu_state,buff_beep_enable;
    if(ros_interface.GetJsonCtrlFlag() == true)
    {
        m_data_json = ros_interface.GetJsonCtrlMsg();
        ros_interface.ResetJsonCtrlFlag();
        ros_interface.ClearJsonCtrlMsg();
        DynamicJsonDocument doc(512);
        deserializeJson(doc, m_data_json);
        if(doc.containsKey("manu_enable"))buff_manu_enable = doc["manu_enable"];
        else buff_manu_enable = m_dev_info.charger_work_mode;
        if(doc.containsKey("manu_state"))buff_manu_state = doc["manu_state"];
        else buff_manu_state = ros_interface.m_manu_state;
        if(doc.containsKey("beep_enable"))buff_beep_enable = doc["beep_enable"];
        else buff_beep_enable = m_dev_info.charger_beep_state;

        if(buff_manu_enable != m_dev_info.charger_work_mode || buff_manu_state != ros_interface.m_manu_state || buff_beep_enable != m_dev_info.charger_beep_state)
        {
            ChargeSetState(buff_manu_enable,buff_manu_state,buff_beep_enable,m_dev_info.charger_rec_vol,m_dev_info.charger_min_cur);
        }
    }
}
/*------------------------------------------------------------------------------------------------------------------
 * name: ComDataIn
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::ComDataIn()
{
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    if(ros_interface.GetComXstdFlag() == 0)return;
    vector<XstdData> data_com_list = ros_interface.GetComXstdMsg();
    XstdData data_recv;
    short temp;
    for(unsigned long i=0;i<data_com_list.size();i++)
    {
        data_recv = data_com_list.at(i);
        if(data_recv.id_c != DEV_CLASS) continue;
        m_dev_info.s_num = data_recv.id_n;
        m_dev_info.s_type = data_recv.id_t;
        switch(data_recv.id_f)
        {
            /************************firmware version***************************************/
            case 0xA2:
                m_dev_info.s_ver_hard = std::to_string(data_recv.data[3]) + std::to_string(data_recv.data[2]) + "." + std::to_string(data_recv.data[1]) + std::to_string(data_recv.data[0]);
                m_dev_info.s_ver_soft = std::to_string(data_recv.data[7]) + std::to_string(data_recv.data[6]) + "." + std::to_string(data_recv.data[5]) + std::to_string(data_recv.data[4]);
            break;
            /************************heart beat***************************************/
            case 0xB0:
                m_dev_info.s_en_state = data_recv.data[0];
                m_online_count = 200;
                f_online = true;
            break;
            /************************BMS info***************************************/
            case 0xB1:
                m_dev_info.BMS_work_state = data_recv.data[0];
                m_dev_info.BMS_charge_state = data_recv.data[3];

                m_dev_info.BMS_warning_over_vol = data_recv.data[1] & 0x01;
                m_dev_info.BMS_warning_low_vol = (data_recv.data[1]>>1) & 0x01;
                m_dev_info.BMS_warning_over_heat = (data_recv.data[1]>>2) & 0x01;
                m_dev_info.BMS_warning_low_heat = (data_recv.data[1]>>3) & 0x01;
                m_dev_info.BMS_warning_over_discharge = (data_recv.data[1]>>4) & 0x01;
                m_dev_info.BMS_warning_over_charge = (data_recv.data[1]>>5) & 0x01;
                m_dev_info.BMS_warning_low_battery = (data_recv.data[1]>>6) & 0x01;

                m_dev_info.BMS_protect_over_vol = data_recv.data[2] & 0x01;
                m_dev_info.BMS_protect_low_vol = (data_recv.data[2]>>1) & 0x01;
                m_dev_info.BMS_protect_over_heat = (data_recv.data[2]>>2) & 0x01;
                m_dev_info.BMS_protect_low_heat = (data_recv.data[2]>>3) & 0x01;
                m_dev_info.BMS_protect_over_discharge = (data_recv.data[2]>>4) & 0x01;
                m_dev_info.BMS_protect_over_charge = (data_recv.data[2]>>5) & 0x01;
                m_dev_info.BMS_protect_low_battery = (data_recv.data[2]>>6) & 0x01;
                m_dev_info.BMS_protect_short = (data_recv.data[2]>>7) & 0x01;
            break;
            /************************BMS data*************************************/
            case 0xB2:
                m_dev_info.BMS_SOC = data_recv.data[0];
                m_dev_info.BMS_SOH = data_recv.data[1];
                memcpy(&temp,&data_recv.data[2],2);
                m_dev_info.BMS_vol = static_cast<float>(temp)/100;
                memcpy(&temp,&data_recv.data[4],2);
                m_dev_info.BMS_cur = static_cast<float>(temp)/10;
                memcpy(&temp,&data_recv.data[6],2);
                m_dev_info.BMS_heat = static_cast<float>(temp)/10;
            break;
            /*****************************charger info********************************/
            case 0xB3:
                m_dev_info.charger_work_mode = data_recv.data[0];
                m_dev_info.charger_work_state = data_recv.data[2];
                m_dev_info.charger_touch_state = data_recv.data[1];
                m_dev_info.charger_error_state = data_recv.data[3];
                m_dev_info.charger_beep_state = data_recv.data[4];
                m_dev_info.charger_rec_vol = static_cast<float>(data_recv.data[5])/10;
                m_dev_info.charger_min_cur = static_cast<float>(data_recv.data[6])/10;
            break;
            /*****************************charger info********************************/
            case 0xB4:
            memcpy(&temp,&data_recv.data[0],2);
            m_dev_info.charger_vol = static_cast<float>(temp)/100;
            memcpy(&temp,&data_recv.data[2],2);
            m_dev_info.charger_cur = static_cast<float>(temp)/10;
            break;
            default:
            break;
        }
    }
    ros_interface.ResetComXstdFlag();
    ros_interface.ClearComXstdMsg();
}
/*------------------------------------------------------------------------------------------------------------------
 * name: DevReset
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::DevReset()
{
    XstdData order;
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    order.id_c = DEV_CLASS;
    order.id_t = m_dev_info.s_type;
    order.id_n = m_dev_info.s_num;
    order.id_f = 0x01;
    order.len = 3;
    order.data[0] = DEV_CLASS;
    order.data[1] = m_dev_info.s_type;
    order.data[2] = m_dev_info.s_num;
    ros_interface.PubComXstd(order);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: DevClear
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::DevClear()
{
    XstdData order;
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    order.id_c = DEV_CLASS;
    order.id_t = m_dev_info.s_type;
    order.id_n = m_dev_info.s_num;
    order.id_f = 0x04;
    order.len = 1;
    order.data[0] = 0xCC;
    ros_interface.PubComXstd(order);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: DevVersion
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::DevVersion()
{
    XstdData order;
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    order.id_c = DEV_CLASS;
    order.id_t = m_dev_info.s_type;
    order.id_n = m_dev_info.s_num;
    order.id_f = 0x02;
    order.len = 0;
    ros_interface.PubComXstd(order);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: DevSetState
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::DevSetEnable(bool en)
{
    XstdData order;
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    order.id_c = DEV_CLASS;
    order.id_t = m_dev_info.s_type;
    order.id_n = m_dev_info.s_num;
    order.id_f = 0x03;
    order.len = 5;
    order.data[0] = DEV_CLASS;
    order.data[1] = m_dev_info.s_type;
    order.data[2] = m_dev_info.s_num;
    order.data[3] = en;
    order.data[4] = m_dev_info.s_num;
    ros_interface.PubComXstd(order);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: ChargeSetState
 -----------------------------------------------------------------------------------------------------------------*/
void PowerFunc::ChargeSetState(unsigned char mode,unsigned char manual,bool beep,float vol,float cur)
{
    XstdData order;
    ROSInterface& ros_interface = ROSInterface::GetInterface();
    order.id_c = DEV_CLASS;
    order.id_t = m_dev_info.s_type;
    order.id_n = m_dev_info.s_num;
    order.id_f = 0x13;
    order.len = 5;
    order.data[0] = mode;
    order.data[1] = manual;
    order.data[2] = beep;
    order.data[3] = static_cast<unsigned char>(vol*10);
    order.data[4] = static_cast<unsigned char>(cur*10);
    ros_interface.PubComXstd(order);
}
