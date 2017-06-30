# app_thin_unused_method
> app thin:remove unused methods by run the python script 

## 脚本使用说明：
python ios.py linkmap_path project_path pod_path >> python_log.txt

举个例子：python ios.py '/Users/wangdt/python/linkMap.txt' '/Users/wangdt/WBG/3.2/oa' '/Users/wangdt/WBG/3.2/Pods/' >> python_log.txt

参数说明
0: ios.py,	【必填】脚本的路径

1: linkmap_path，	【必填】项目编译后生成的linkmap文件的路径（你可以复制出来，方便调试）

2: project_path，	【必填】项目的根路径，用来遍历你的整个项目（你可以选择某个文件夹）

3: pod_path，	【选填】用来统计第三方库中的class_name_list，过滤掉uncalled_method

## 问题：
该脚本把过滤出来的unused methods 放在python_log.txt 里，这里的数据并不是全部都是unused methods,有一部分是由于我写的正则表示过滤数据不完整造成的，你需要确认后再删除unused methods