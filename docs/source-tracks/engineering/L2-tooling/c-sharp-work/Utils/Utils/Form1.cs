using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Utils
{
    public partial class Form1 : Form
    {
        public Form1()
        {
            InitializeComponent();
        }

        private void button1_Click(object sender, EventArgs e)
        {
            //Message();
            //Save();
            //Open();
            OpenFolder();
        }

        /// <summary>
        ///消息提示框 
        /// </summary>
        public void Message()
        {
            //消息提示框：提示信息，标题，图标，确认，退出
            if (MessageBox.Show("确认退出吗？", "警告",
                                                 MessageBoxButtons.OKCancel,MessageBoxIcon.Question) == DialogResult.OK)
            {
                // do something
            }
        }

        /// <summary>
        /// 获取保存文件名
        /// </summary>
        /// <returns>文件名</returns>
        public string Save()
        {
            SaveFileDialog sfd = new SaveFileDialog();
            sfd.Filter = "txt|*.txt|json|*.json|xml|*.xml";
            sfd.Title = "save a file";
            if (sfd.ShowDialog() == DialogResult.OK)
                return sfd.FileName;

            return null;
        }

        /// <summary>
        /// 打开文件
        /// </summary>
        /// <returns>文件名</returns>
        public string Open()
        {
            OpenFileDialog ofd = new OpenFileDialog();
            if (ofd.ShowDialog() == DialogResult.OK)
                return ofd.FileName;

            return null;
        }
      
        /// <summary>
        /// 打开文件夹
        /// </summary>
        /// <returns></returns>
        public string OpenFolder()
        {
            FolderBrowserDialog fbd = new FolderBrowserDialog();
            if (fbd.ShowDialog() == DialogResult.OK)
                return fbd.SelectedPath;

            return null;
        }

        /// <summary>
        /// 读出目录下的所有文件名
        /// </summary>
        /// <param name="directory"></param>
        public void ListDirectory(string directory)
        {
            string[] files = Directory.GetFiles(directory);
        }

        /// <summary>
        /// 读取文件
        /// </summary>
        /// <param name="path">文件路径</param>
        public void Read(string path)
        {
            StreamReader sr = new StreamReader(path, Encoding.Default);
            String line="";
            while ((line = sr.ReadLine()) != null)
            {
                Console.WriteLine(line.ToString());
            }
        }

        /// <summary>
        /// 写入文件
        /// </summary>
        /// <param name="path">文件路径</param>
        /// <param name="content">要写入的字符</param>
        public void Write(string path,string content)
        {
            FileStream fs = new FileStream(path,FileMode.OpenOrCreate,FileAccess.ReadWrite);
            StreamWriter sw = new StreamWriter(fs,Encoding.UTF8);
            sw.Write(content);
            sw.Flush();
            sw.Close();
            fs.Close();
        }

        /// <summary>
        /// 线程
        /// </summary>
        public void TaskTest()
        {
            /*
             * 多线程的重点是任务划分，划分为互不干扰的多个任务
             * 即各变量之间没有依赖关系或依赖关系可通过信号量和锁等机制进行通信控制
             */


            Task task = new Task(()=>
            {
                //do something
            });
            task.Start();
            while (!task.IsCompleted)
            {
                Thread.Sleep(10);
                Application.DoEvents();
            }
            if (task.IsCompleted)
            {
                //do another thing
            }
            Task task1 = Task.Factory.StartNew(()=>
            {
                //do something
            });
            Task task2 = Task.Factory.StartNew(() =>
            {
                //do something
            });
            Task.WaitAll(task,task1,task2);
            bool done = false;
            Thread thread = new Thread(()=>
            {
                //do something
                done = true;
            });
            //设置后台运行，常用于ui交互
            thread.IsBackground = true;
            thread.Start();
            while (!done)
            {
                Thread.Sleep(5);
                Application.DoEvents();
            }
        }

    }
}
