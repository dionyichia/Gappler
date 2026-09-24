#include <ros_interface.h>

namespace XROS_POWER
{
void ROSInterface::BaseInit(int argc, char* argv[], std::string node_name,double period, void (*handle)())
{
    ros::init(argc, argv, node_name);
    static ros::NodeHandle nh;
    static ros::NodeHandle nh_local("~");
    m_node_ptr = &nh;
    m_node_local_ptr = &nh_local;
    VariableInit();
    ParameterInit();
    PublisherInit();
    SubscriptionInit();
    TimerInit(period, handle);
    ROSLog(LogLevel::kInfo,"\033[1;32m %s: ### ROS interface init finish ### \033[0m",node_name.data());
}
/*------------------------------------------------------------------------------------------------------------------
 * name: BaseDeinit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::BaseDeinit()
{
    Shutdown();
}
/*------------------------------------------------------------------------------------------------------------------
 * name: GetInterface
 -----------------------------------------------------------------------------------------------------------------*/
ROSInterface& ROSInterface::GetInterface()
{
    static ROSInterface ros_interface;
    return ros_interface;
}
/*------------------------------------------------------------------------------------------------------------------
 * name: ROSLog
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::ROSLog(LogLevel level, const char* format, ...)
{
    char* buffer;

    va_list args;
    va_start(args, format);
    int32_t len = vasprintf(&buffer, format, args);
    va_end(args);

    if (len < 0)
    {
        ROS_FATAL("### Wrong Log Message ###");
        return;
    }

    switch (level)
    {
    case LogLevel::kDebug:
        ROS_DEBUG("%s", buffer);
        break;
    case LogLevel::kInfo:
        ROS_INFO("%s", buffer);
        break;
    case LogLevel::kWarn:
        ROS_WARN("%s", buffer);
        break;
    case LogLevel::kError:
        ROS_ERROR("%s", buffer);
        break;
    case LogLevel::kFatal:
        ROS_FATAL("%s", buffer);
        break;
    default:
        ROS_FATAL("### Wrong Log Level ###");
        ROS_FATAL("%s", buffer);
        break;
    }
    free(buffer);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: TimerInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::TimerInit(double period, void (*handle)())
{
    m_timer_handle = handle;
    m_timer = m_node_ptr->createTimer(ros::Duration(period * 0.001),&ROSInterface::TimerCallback, this);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: NodeCheck
 -----------------------------------------------------------------------------------------------------------------*/
bool ROSInterface::NodeCheck(std::string node_name)
{
    std::vector<std::string> nodes;
    ros::master::getNodes(nodes);
    for(int i=0;i<nodes.size();i++)
    {
       // ROSLog(LogLevel::kInfo," <%s> ",nodes[i].data());
        if (nodes[i] == "/"+node_name)return true;
    }
    return false;
}
/*------------------------------------------------------------------------------------------------------------------
 * name: ParameterInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::ParameterInit()
{
    m_node_local_ptr->getParam("ini_path", m_ini_path);
    m_node_local_ptr->param("manu_enable", m_manu_enable, false);
    m_node_local_ptr->param("manu_state", m_manu_state, false);
    m_node_local_ptr->param("test_mode", m_test_mode, false);
    m_node_local_ptr->param("beep_enable", m_beep_enable, true);
    m_node_local_ptr->param("rec_voltage", m_rec_voltage, 1.0);
    m_node_local_ptr->param("min_current", m_min_current, 0.2);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: VariableInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::VariableInit()
{
  m_manu_enable = false;
  m_manu_state = false;
  m_test_mode = false;
  m_beep_enable = true;
  m_rec_voltage = 1.0;
  m_min_current = 0.2;
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PublisherInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PublisherInit()
{
  pub_com_xstd = m_node_local_ptr->advertise<xpkg_msgs::XmsgCommData>("/xtopic_comm/com_send_xstd", 50);
  pub_vel = m_node_local_ptr->advertise<geometry_msgs::Twist>("/cmd_vel", 1);
  pub_device_state = m_node_local_ptr->advertise<std_msgs::String>("/xtopic_power/device_state_json", 50);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: SubscriptionInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::SubscriptionInit()
{ 
  sub_com_xstd = m_node_local_ptr->subscribe("/xtopic_comm/com_recv_xstd_power", 50, &ROSInterface::ComXstdCallback, this);
  sub_json_ctrl = m_node_local_ptr->subscribe("/xtopic_power/ctrl_json", 50, &ROSInterface::JsonCtrlCallback, this);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PubComXstd
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PubComXstd(const XstdData& data)
{
    xpkg_msgs::XmsgCommData data_com;
    data_com.len = data.len;
    data_com.id_c = data.id_c;
    data_com.id_t = data.id_t;
    data_com.id_n = data.id_n;
    data_com.id_f = data.id_f;
    memcpy(&data_com.data[0],&data.data[0],data.len);
    data_com.time = ros::Time::now();
    pub_com_xstd.publish(data_com);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PubDevState
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PubDevState(const std::string& data)
{
    std_msgs::String buff;
    buff.data.append(data);
    pub_device_state.publish(buff);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PubVel
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PubVel(const double& speed_x,const double& speed_y,const double& speed_r)
{
    geometry_msgs::Twist speed;
    speed.linear.x = speed_x;
    speed.linear.y = speed_y;
    speed.angular.z = speed_r;
    pub_vel.publish(speed);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: sub callback
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::ComXstdCallback(const xpkg_msgs::XmsgCommDataPtr& data)
{
  m_f_com_xstd = true;
  XstdData data_com;
  data_com.len = data->len;
  data_com.id_c = data->id_c;
  data_com.id_t = data->id_t;
  data_com.id_n = data->id_n;
  data_com.id_f = data->id_f;
  memcpy(&data_com.data[0],&data->data[0],data->len);
  data_com.time = data->time.toSec();
  m_list_com_xstd.push_back(data_com);
  if(m_list_com_xstd.size()>500)m_list_com_xstd.clear();
}

///////////////////////////////////////////////////////////////////////////////////////////////
void ROSInterface::JsonCtrlCallback(const std_msgs::StringPtr& data)
{
  m_f_json_ctrl = true;
  m_json_ctrl.append(data->data);
  if(m_json_ctrl.size()>50000)
  {
      m_json_ctrl.clear();
      ROSLog(LogLevel::kWarn,"%ROS1_interface: json ctrl msg is full,please reduce the publishing frequency");
  }
}

}//namespace XROS_POWER
