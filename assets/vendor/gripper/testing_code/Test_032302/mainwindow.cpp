#include "mainwindow.h"
#include "ui_mainwindow.h"

MainWindow::MainWindow(QWidget *parent) :
    QMainWindow(parent),
    ui(new Ui::MainWindow)
{
    ui->setupUi(this);
}

MainWindow::~MainWindow()
{
    delete ui;
}


void MainWindow::on_Disconnect_clicked()
{
    // 关闭连接
    Arm_Socket_Close(m_sockhand);
}

void MainWindow::on_Test_MoveJ_clicked()
{
    int ret;

    float joint[6] = {0,0,0,0,0,0};
    float joint1[6] = {0,0,90,0,90,0};
    ret = Movej_Cmd(m_sockhand,joint1,30,0,1);
    ui->textEdit->append(QString("机械臂运动第1个点").arg(ret));
    ret =Movej_Cmd(m_sockhand,joint,30,0,1);
    ui->textEdit->append(QString("机械臂运动第2个点").arg(ret));
}

void MainWindow::on_connect_Socket_clicked()
{

    // 连接服务器 返回全局句柄
    RM_API_Init(65,NULL);
    m_sockhand = Arm_Socket_Start((char *)"192.168.1.18", 8080, 5000);

}


