#include <rclcpp/rclcpp.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages.h>
#include <moveit/task_constructor/solvers.h>

using namespace moveit::task_constructor;

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = rclcpp::Node::make_shared("mtc_sim_test",
                                        rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true));

  // Spin node in background so MoveIt2 can receive robot state
  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node);
  auto spin_thread = std::thread([&exec]()
                                 { exec.spin(); });

  // ----- Task setup -----
  Task task;
  task.stages()->setName("sim_test_task");
  task.loadRobotModel(node);

  const std::string ARM_GROUP = "rm_group";
  const std::string GRIPPER_GROUP = "gripper";

  auto arm_planner = std::make_shared<solvers::JointInterpolationPlanner>();
  auto gripper_planner = std::make_shared<solvers::JointInterpolationPlanner>();

  // ---- Stage 0: Current state ----
  {
    auto stage = std::make_unique<stages::CurrentState>("current state");
    task.add(std::move(stage));
  }

  // ---- Stage 1: Open gripper ----
  {
    auto stage = std::make_unique<stages::MoveTo>("open gripper", gripper_planner);
    stage->setGroup(GRIPPER_GROUP);
    stage->setGoal("open");
    task.add(std::move(stage));
  }

  // ---- Stage 2: Move arm to test pose ----
  {
    auto stage = std::make_unique<stages::MoveTo>("move to test pose", arm_planner);
    stage->setGroup(ARM_GROUP);
    std::map<std::string, double> target_joints = {
        {"joint1", 0.5},
        {"joint2", -0.5},
        {"joint3", 0.0},
        {"joint4", 0.0},
        {"joint5", 0.0},
        {"joint6", 0.0},
    };
    stage->setGoal(target_joints);
    task.add(std::move(stage));
  }

  // ---- Stage 3: Close gripper ----
  {
    auto stage = std::make_unique<stages::MoveTo>("close gripper", gripper_planner);
    stage->setGroup(GRIPPER_GROUP);
    stage->setGoal("close");
    task.add(std::move(stage));
  }

  // ---- Stage 4: Return arm to home ----
  {
    auto stage = std::make_unique<stages::MoveTo>("return home", arm_planner);
    stage->setGroup(ARM_GROUP);
    std::map<std::string, double> home_joints = {
        {"joint1", 0.0},
        {"joint2", 0.0},
        {"joint3", 0.0},
        {"joint4", 0.0},
        {"joint5", 0.0},
        {"joint6", 0.0},
    };
    stage->setGoal(home_joints);
    task.add(std::move(stage));
  }

  // ---- Stage 5: Open gripper ----
  {
    auto stage = std::make_unique<stages::MoveTo>("open gripper final", gripper_planner);
    stage->setGroup(GRIPPER_GROUP);
    stage->setGoal("open");
    task.add(std::move(stage));
  }

  // ----- Plan and execute -----
  try
  {
    RCLCPP_INFO(node->get_logger(), "Initializing task...");
    task.enableIntrospection(true);
    task.init();
    if (!task.plan(5))
    {
      RCLCPP_ERROR(node->get_logger(), "Task planning failed");
      rclcpp::shutdown();
      spin_thread.join();
      return 1;
    }
    RCLCPP_INFO(node->get_logger(), "Planning succeeded, executing...");
    task.execute(*task.solutions().front());
  }
  catch (const InitStageException &e)
  {
    RCLCPP_ERROR_STREAM(node->get_logger(), "Stage init failed: " << e);
  }

  rclcpp::shutdown();
  spin_thread.join();
  return 0;
}
