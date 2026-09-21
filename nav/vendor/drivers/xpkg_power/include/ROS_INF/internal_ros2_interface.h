#pragma once
#ifndef INTERNAL_ROS2_INTERFACE_H
#define INTERNAL_ROS2_INTERFACE_H

#include <string>
#include <vector>
#include <memory>
#include <rclcpp/rclcpp.hpp>
#include <stdarg.h>

//add message include below////////////////////////////////
#include <xpkg_msgs/msg/xmsg_comm_data.hpp>
#include <std_msgs/msg/string.hpp>
#include <geometry_msgs/msg/twist.hpp>

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
    inline void Work() {rclcpp::spin(m_node_ptr);}
    inline void Shutdown() {rclcpp::shutdown();}
    inline bool Ok() {return rclcpp::ok();}
    inline rclcpp::Time GetTime(){return m_node_ptr->now();};
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
    inline void TimerCallback() { m_timer_handle(); }

  private:
    std::shared_ptr<rclcpp::Node> m_node_ptr;
    rclcpp::TimerBase::SharedPtr m_timer;
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
    void ComXstdCallback(const xpkg_msgs::msg::XmsgCommData::SharedPtr data);
    void JsonCtrlCallback(const std_msgs::msg::String::SharedPtr data);

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
    rclcpp::Publisher<xpkg_msgs::msg::XmsgCommData>::SharedPtr pub_com_xstd;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_device_state;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr pub_vel;

    //add sub Variable below/////////////////////////////////
    rclcpp::Subscription<xpkg_msgs::msg::XmsgCommData>::SharedPtr sub_com_xstd;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_json_ctrl;

    //add normal Variable below///////////////////////////////
    vector<XstdData> m_list_com_xstd;
    std::string m_json_ctrl;
};

}//namespace XROS_POWER
#endif // INTERNAL_ROS2_INTERFACE_H
