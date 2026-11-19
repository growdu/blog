# include<stdio.h>
# include<stdlib.h>

//获得结构体（TYPE）的变量成员（MEMBER）在此结构体中的偏移量
#define offsetof(TYPE,MEMBER) ((size_t) &((TYPE*)0)->MEMBER)

//根据结构体（type）变量中的域变量成员（member）的指针（ptr）来获取整个结构体变量的指针
#define container_of(ptr,type,member) ({ \
		const typeof(((type*)0)->member) * _mptr=(ptr);\
		(type *) ((char *)_mptr-offsetof(type,member));\
		})

typedef struct list{
	int n;
	struct list* next;
}*plist,list;

plist init(){
	plist p;
	p=(plist)malloc(sizeof(list));
	if(p==NULL){
		printf("malloc failed.");
	}
	p->n=0;
	p->next=NULL;
	return p;
}

int main(int argc,char *argv[]){
	plist l=init();
	l->n=50;
	l->next=l;
	//分别输出结构体的数据n以及指向自己的指针，偏移量，整型的长度，结构体的地址
	printf("%d,%p,%ld,%ld,%p\n",l->n,l->next,offsetof(struct list,next),sizeof(int),container_of(&l->next,struct list,next));
	free(l);
}



