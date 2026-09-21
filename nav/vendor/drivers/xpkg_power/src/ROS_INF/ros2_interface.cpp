#include <ros_interface.h>

namespace XROS_POWER
{
/*------------------------------------------------------------------------------------------------------------------
 * name: BaseInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::BaseInit(int argc, char* argv[], std::string node_name,double period, void (*handle)())
{
  rclcpp::init(argc, argv);
  m_node_ptr = std::make_shared<rclcpp::Node>(node_name);

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
  // timer
  m_timer.reset();
  
  // pub
  pub_com_xstd.reset();
  pub_device_state.reset();

  // sub
  sub_com_xstd.reset();
  sub_json_ctrl.reset();
  
  // node
  m_node_ptr.reset();
  
  // shutdown
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
    RCLCPP_FATAL(m_node_ptr->get_logger(), "### Wrong Log Message ###");
    return;
  }

  switch (level)
  {
    case LogLevel::kDebug:
      RCLCPP_DEBUG(m_node_ptr->get_logger(), "%s", buffer);
      break;
    case LogLevel::kInfo:
      RCLCPP_INFO(m_node_ptr->get_logger(), "%s", buffer);
      break;
    case LogLevel::kWarn:
      RCLCPP_WARN(m_node_ptr->get_logger(), "%s", buffer);
      break;
    case LogLevel::kError:
      RCLCPP_ERROR(m_node_ptr->get_logger(), "%s", buffer);
      break;
    case LogLevel::kFatal:
      RCLCPP_FATAL(m_node_ptr->get_logger(), "%s", buffer);
      break;
    default:
      RCLCPP_FATAL(m_node_ptr->get_logger(), "### Wrong Log Level ###");
      RCLCPP_FATAL(m_node_ptr->get_logger(), "%s", buffer);
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
  m_timer = m_node_ptr->create_wall_timer(std::chrono::milliseconds(static_cast<int64_t>(period)), std::bind(&ROSInterface::TimerCallback, this));
}
/*------------------------------------------------------------------------------------------------------------------
 * name: NodeCheck
 -----------------------------------------------------------------------------------------------------------------*/
bool ROSInterface::NodeCheck(std::string node_name)
{
    std::vector<std::string> nodes = m_node_ptr->get_node_names();
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
  m_node_ptr->declare_parameter<std::string>("ini_path", "");
  m_node_ptr->declare_parameter<bool>("manu_enable", false);
  m_node_ptr->declare_parameter<bool>("manu_state", false);
  m_node_ptr->declare_parameter<bool>("test_mode", false);
  m_node_ptr->declare_parameter<bool>("beep_enable", true);
  m_node_ptr->declare_parameter<float>("rec_voltage", 1.0);
  m_node_ptr->declare_parameter<float>("min_current", 0.2);

  m_node_ptr->get_parameter("ini_path", m_ini_path);
  m_node_ptr->get_parameter("manu_enable", m_manu_enable);
  m_node_ptr->get_parameter("manu_state", m_manu_state);
  m_node_ptr->get_parameter("test_mode", m_test_mode);
  m_node_ptr->get_parameter("beep_enable", m_beep_enable);
  m_node_ptr->get_parameter("rec_voltage", m_rec_voltage);
  m_node_ptr->get_parameter("min_current", m_min_current);
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
    pub_com_xstd = m_node_ptr->create_publisher<xpkg_msgs::msg::XmsgCommData>("/xtopic_comm/com_send_xstd", 50);
    pub_device_state = m_node_ptr->create_publisher<std_msgs::msg::String>("/xtopic_power/device_state_json", 50);
    pub_vel = m_node_ptr->create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 1);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: SubscriptionInit
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::SubscriptionInit()
{ 
    sub_com_xstd = m_node_ptr->create_subscription<xpkg_msgs::msg::XmsgCommData>("/xtopic_comm/com_recv_xstd_switch", 50, std::bind(&ROSInterface::ComXstdCallback, this, std::placeholders::_1));
    sub_json_ctrl = m_node_ptr->create_subscription<std_msgs::msg::String>("/xtopic_power/ctrl_json", 50, std::bind(&ROSInterface::JsonCtrlCallback, this, std::placeholders::_1));
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PubComXstd
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PubComXstd(const XstdData& data)
{
    xpkg_msgs::msg::XmsgCommData data_com;
    data_com.len = data.len;
    data_com.id_c = data.id_c;
    data_com.id_t = data.id_t;
    data_com.id_n = data.id_n;
    data_com.id_f = data.id_f;
    memcpy(&data_com.data[0],&data.data[0],data.len);
    data_com.time = m_node_ptr->now();
    pub_com_xstd->publish(data_com);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PubDevState
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PubDevState(const std::string& data)
{
    std_msgs::msg::String buff;
    buff.data.append(data);
    pub_device_state->publish(buff);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: PubVel
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::PubVel(const double& speed_x,const double& speed_y,const double& speed_r)
{
    geometry_msgs::msg::Twist speed;
    speed.linear.x = speed_x;
    speed.linear.y = speed_y;
    speed.angular.z = speed_r;
    pub_vel->publish(speed);
}
/*------------------------------------------------------------------------------------------------------------------
 * name: ComXstdCallback
 -----------------------------------------------------------------------------------------------------------------*/
void ROSInterface::ComXstdCallback(const xpkg_msgs::msg::XmsgCommData::SharedPtr data)
{
  m_f_com_xstd = true;
  XstdData data_com;
  data_com.len = data->len;
  data_com.id_c = data->id_c;
  data_com.id_t = data->id_t;
  data_com.id_n = data->id_n;
  data_com.id_f = data->id_f;
  memcpy(&data_com.data[0],&data->data[0],data->len);
  data_com.time = m_node_ptr->now().seconds();
  m_list_com_xstd.push_back(data_com);
  if(m_list_com_xstd.size()>500)m_list_com_xstd.clear();
}
///////////////////////////////////////////////////////////////////////////////////////////////
void ROSInterface::JsonCtrlCallback(const std_msgs::msg::String::SharedPtr data)
{
  m_f_json_ctrl = true;
  m_json_ctrl.append(data->data);
  if(m_json_ctrl.size()>50000)
  {
      m_json_ctrl.clear();
      ROSLog(LogLevel::kWarn,"%ROS2_interface: json ctrl msg is full,please reduce the publishing frequency");
  }
}


}//namespace XROS_POWER
