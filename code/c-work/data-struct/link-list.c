# include<stdio.h>
# include<stdlib.h>

typedef struct list{
	int n;
	struct list* next;
}*plist,list;

plist init(){
	list* p;
	p=(list *)malloc(sizeof(list));
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
	printf("%n,%p\n",l->n,l->next);
}



