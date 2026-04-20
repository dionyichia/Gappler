#pragma once
#ifndef INTERNAL_ROS1_INTERFACE_H
#define INTERNAL_ROS1_INTERFACE_H

#include <string>
#include <vector>
#include <memory>
#include <ros/ros.h>
#include <stdarg.h>

//add message include below////////////////////////////////
#include <xpkg_msgs/XmsgCommData.h>
#include <std_msgs/String.h>
#include<geometry_msgs/Twist.h>


using namespace std;
namespace XROS_POWER
{
////////////////////////////////////////////////////////////
enum class LogLevel
{
  kDebug = 0,
  kInfo,
  kWarn,
  kError,
  kFatal
};
struct XstdData
{
  unsigned char id_c;
  unsigned char id_t;
  unsigned char id_n;
  unsigned char id_f;
  unsigned char len;
  unsigned char data[8];
  double time;
};
////////////////////////////////////////////////////////////
class ROSInterface
{
  /*********************************************************
                    Base function zone
  *********************************************************/
  public:
    static ROSInterface& GetInterface();
    void BaseInit(int argc, char* argv[], std::string node_name,double period, void (*handle)());
    void BaseDeinit();
    inline void Work() {ros::spin();}
    inline void Shutdown() {ros::shutdown();}
    inline bool Ok() {return ros::ok();}
    inline ros::Time GetTime(){return ros::Time::now();};
    void ROSLog(LogLevel, const char*, ...);
    bool NodeCheck(std::string node_name);

  private:
    ROSInterface() = default;
    virtual ~ROSInterface() = default;
    void VariableInit();
    void ParameterInit();
    void PublisherInit();
    void SubscriptionInit();
    void TimerInit(double period, void (*handle)());

  protected:
    inline void TimerCallback(const ros::TimerEvent&) { m_timer_handle(); }

  private:
    ros::NodeHandle* m_node_ptr;
    ros::NodeHandle* m_node_local_ptr;
    ros::Timer m_timer;
    void (*m_timer_handle)();

  /*********************************************************
                        Custom zone
  *********************************************************/
  public:
    //add pub function below////////////////////////////////
    void PubComXstd(const XstdData& data);
    void PubVel(const double& speed_x,const double& speed_y,const double& speed_r);
    void PubDevState(const std::string& data);

    //add sub function below////////////////////////////////
    inline bool GetComXstdFlag() { return m_f_com_xstd; }
    inline bool GetJsonCtrlFlag() { return m_f_json_ctrl; }
    inline void ResetComXstdFlag() { m_f_com_xstd = false; }
    inline void ResetJsonCtrlFlag() { m_f_json_ctrl = false; }
    inline vector<XstdData> GetComXstdMsg() { return m_list_com_xstd; }
    inline std::string GetJsonCtrlMsg() { return m_json_ctrl; }
    inline void ClearComXstdMsg() { m_list_com_xstd.clear(); }
    inline void ClearJsonCtrlMsg() { m_json_ctrl.clear(); }

    //add sub callback below////////////////////////////////////
    void ComXstdCallback(const xpkg_msgs::XmsgCommDataPtr& data);
    void JsonCtrlCallback(const std_msgs::StringPtr& data);

  public:
    //add param Variable below///////////////////////////////
    std::string m_ini_path;
    bool m_manu_enable;
    bool m_manu_state;
    bool m_beep_enable;
    bool m_test_mode;
    double m_rec_voltage;
    double m_min_current;

  private:
    //add sub flag below/////////////////////////////////////
    bool m_f_com_xstd;
    bool m_f_json_ctrl;

    //add pub Variable below/////////////////////////////////
    ros::Publisher pub_com_xstd;
    ros::Publisher pub_vel;
    ros::Publisher pub_device_state;

    //add sub Variable below/////////////////////////////////
    ros::Subscriber sub_com_xstd;
    ros::Subscriber sub_json_ctrl;

    //add nomal Variable below///////////////////////////////
    vector<XstdData> m_list_com_xstd;
    std::string m_json_ctrl;
};

}//namespace XROS_POWER
#endif // INTERNAL_ROS1_INTERFACE_H
