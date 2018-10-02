/*************************************
 *浣滆€咃細growdu
 *鏃ユ湡锛?018-10-01
 *鍔熻兘锛氳绠楁椂鏃跺僵鍚勭鎯呭喌鐨勫嚭鐜版鏁?
 *璇存槑锛氭椂鏃跺僵浠婚€?涓?-9涔嬮棿鐨勬暟瀛楄繘琛岀粍鍚堬紝鍏辨湁浜旂鎯呭喌锛?
 *璞瑰瓙銆侀『瀛愩€佸崐椤恒€佸瀛愩€佹潅鍏?
 *************************************/
#include<stdio.h>
#include<stdlib.h>

int main(void){
	int result[5]={0};
    float expect[5]={};
    int total=1000;
    float sumExpect=0;
    for(int i=0;i<10;i++){
        for(int j=0;j<10;j++){
            for(int n=0;n<10;n++){
                if(i==j&&j==n&&i==n)
                    result[0]++;

                else if(abs(i-j)==1&&abs(j-n)==1
                            ||
                        abs(i-n)==1&&abs(i-j)==1
                        )
                    result[1]++;

                else if(i==j||j==n||i==n)
                    result[2]++;

                else if(abs(i-j)>1&&abs(i-n)>1&&abs(j-n)>1)
                    result[4]++;

                else
                    result[3]++;
            }
        }
        expect[0]=75*result[0]*0.001;
        expect[1]=14.5*result[1]*0.001;
        expect[2]=3.3*result[2]*0.001;
        expect[3]=3*result[3]*0.001;
        expect[4]=2.5*result[4]*0.001;
        for(int i=0;i<5;i++){
            sumExpect+=expect[i];
        }
    }
    printf("%d,%f,%f\n",result[0],result[0]*0.001, expect[0]);
    printf("%d,%f,%f\n",result[1],result[1]*0.001, expect[1]);
    printf("%d,%f,%f\n",result[2],result[2]*0.001, expect[2]);
    printf("%d,%f,%f\n",result[3],result[3]*0.001, expect[3]);
    printf("%d,%f,%f\n",result[4],result[4]*0.001, expect[4]);
    printf("%f\n",sumExpect);
    printf("%f\n",expect[2]+expect[3]+expect[3]);
    return 0;
}