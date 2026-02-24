#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include "rm_base.h"
namespace Ui {
class MainWindow;
}

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = 0);
    ~MainWindow();

private slots:


    void on_Disconnect_clicked();

    void on_Test_MoveJ_clicked();

    void on_connect_Socket_clicked();


private:
    Ui::MainWindow *ui;
    // 手动维护句柄
    SOCKHANDLE m_sockhand = -1;
};

#endif // MAINWINDOW_H
