#!/usr/bin/python
# -*- coding: UTF-8 -*-

# 弊端：（心累了，就写到这吧）
# 	1，不识别大于2个参数的方法调用 [没有找到一些技巧，姑且只能匹配到少于2个参数的方法]
# 	2，不识别protocol的方法调用（包括系统的、自定义的）[可以通过遍历项目得到其方法，然后过滤解决。麻烦！]
# 	3，不识别换行的方法调用 [专门遍历项目，通过"[];"中判断是否为"];"作为结束条件。麻烦！]
# 	4，父类定义的方法，在子类调用，不被识别
# 	5，getter/setter 默认已经被调用，因为在正则匹配 点语法太麻烦了
# 	6，有可能在输出列表中出现一些莫名的类，这个一般是系统类
# 	7，会加载到第三库的方法，这个需要过滤一下，我这边记录了pod文件夹
# 	8，分类的方法按照主类方法处理，比如A+safe的test_safe()，没有被使用，在log信息中会提示A的test_safe没有被调用

# 意义：
# 	1，虽然不能识别那么多方法，但也是可以得到一些简单调用的方法的，可以进行app瘦身
#	2，过程中，对"编码规范、风格统一"有很深的认识（正则表达式）
# 	3，python以及正则的尝试应用

import re
import os
import sys

define_manager_expression_map = {}
subclass_fatherclass_map = {}
class_property_map = {} #{class:[property]}
class_property_type_map = {} # {class:{property:type}}
class_property_setter_getter_map = {}
class_methods_map = {}
called_class_methods_map = {}
uncalled_class_methods_map = {}
special_class_from_third_lib_list = []

def set_dic_strKey_valueList(map,key,item):
	if map.has_key(key):
		method_list = map.get(key)
		# 保证set集合
		if item in method_list:
			pass
		else:
			method_list.append(item)
	else:
		map[key] = [item]

def get_class_methods_map(linkmap_path):
	f = open(linkmap_path)
	for line in f.readlines():
		# 得到class_name : 分类按原类处理
		_list = re.findall(r'\] \-\[(\w+)\(?\w*\)? (.*)\]',line)
		if len(_list) > 0:
			class_name = _list[0][0]
			method_name = _list[0][1]

			# filter setter/getter
			if class_property_setter_getter_map.has_key(class_name):
				if method_name in class_property_setter_getter_map.get(class_name):
					continue
			set_dic_strKey_valueList(class_methods_map,class_name,method_name)
	f.close()

def get_class_ivar_map(linkmap_path):
	f = open(linkmap_path)
	for line in f.readlines():
		_list = re.findall(r'\] _OBJC_IVAR_\$_(\w+)\.\_(\w+)',line)
		if len(_list) > 0:
			class_name = _list[0][0]
			property_name = _list[0][1]
			set_dic_strKey_valueList(class_property_map,class_name,property_name)
	f.close()

def get_class_property_setter_getter_map():
	for item in class_property_map.items():
		class_name = item[0]
		property_list = item[1]
		for property_name in property_list:
			getter = property_name
			firstChar = property_name[0:1].upper()
			otherChars = property_name[1:]
			setter = 'set'+firstChar+otherChars+':'
			set_dic_strKey_valueList(class_property_setter_getter_map,class_name,getter)
			set_dic_strKey_valueList(class_property_setter_getter_map,class_name,setter)

def dirList_walk(fpath):
	result = []
	for path,dir,filelist in os.walk(fpath):
		for filename in filelist:
			filepath = os.path.join(path,filename)
			result.append(filepath)
	return result

def get_called_class_methods_map(path):
	all_file = dirList_walk(path)
	all_file = filter(file_only_m_or_mm,all_file)
	for filepath in all_file:
		# 分类按照原类处理
		file = re.findall(r'.*/(\w+)\+?\w*\.m',filepath)
		if len(file) == 0:
			continue

		#默认为file name
		filename = file[0]
		
		filecontent = open(filepath)
		
		# 每次读取file时，清空intance_class_map
		intance_class_map = {}

		for line in filecontent:
			# 初始化 class_name
			class_name = filename

			# filter 注释掉的代码
			if re.match(r'( *)//',line):
				continue

			#selector
			_a_selector_method_list = re.findall(r'@selector\((\w+:?)\)',line)
			if len(_a_selector_method_list):
				method_name = _a_selector_method_list[0]
				set_dic_strKey_valueList(called_class_methods_map,class_name,method_name)
				continue
			
			# - (IBAction)
			_a_action_method_to_xib_list = re.findall(r'- ?\(IBAction\) ?(\w+:).*',line)
			if len(_a_action_method_to_xib_list) > 0:
				method_name = _a_action_method_to_xib_list[0]
				set_dic_strKey_valueList(called_class_methods_map,class_name,method_name)
				continue

			#过滤掉 特殊的方法[arr addObject:@"123"]
			line = re.sub(r'(\w+ ?addObject(sFromArray)?:)', '', line)
			_list = re.findall(r'(\w+) ?\*(\w+) ?',line)
			if len(_list)>0:
				clazz = _list[0][0]
				instanzz = _list[0][1]
				intance_class_map[instanzz] = clazz

			# 先两个参数，然后...
			class_method_name_map = get_methods_on_line_with2Param(line)
			if len(class_method_name_map) == 0:
				class_method_name_map = get_methods_on_line(line)
			# if len(class_method_name_map) == 0:
			# 	class_method_name_map = get_methods_on_line_2block(line)

			if len(class_method_name_map) > 0:
				clazz_or_instanzz_name = class_method_name_map['clazz_or_instanzz_name']

				# 针对 一个file中只有一个 class时，使用self
				if clazz_or_instanzz_name == 'self' or clazz_or_instanzz_name == 'super':
					class_name = filename
				# 是否为宏定义 #define EventManager [OAEventManager sharedInstance]
				elif define_manager_expression_map.has_key(clazz_or_instanzz_name):
					class_name = define_manager_expression_map[clazz_or_instanzz_name]
				# class or instance ???
				elif clazz_or_instanzz_name[0].isupper():
					class_name = clazz_or_instanzz_name
				else:
					if intance_class_map.has_key(clazz_or_instanzz_name):
						class_name = intance_class_map[clazz_or_instanzz_name]
					else:
						class_name = filename

				class_method_list = class_method_name_map['class_method_list']
				if len(class_method_list) == 1:
					set_dic_strKey_valueList(called_class_methods_map,class_name,class_method_list[0])
				if len(class_method_list) == 2:
					set_dic_strKey_valueList(called_class_methods_map,class_name,class_method_list[1])

			# [[self eventStore] removeAllEvents]; 、[[EventManager eventStore] saveEvents:eventsFromServer];
			_a_class_method_for_getter_map = get_methods_on_line_for_getter(filename,line)
			if len(_a_class_method_for_getter_map) > 0:
				class_name = _a_class_method_for_getter_map['clazz_or_instanzz_name']
				class_method_list = _a_class_method_for_getter_map['class_method_list']
				set_dic_strKey_valueList(called_class_methods_map,class_name,class_method_list[0])

		filecontent.close()

# filter .h .m .mm
def file_only_h(filepath):
	return filepath.endswith('.h');

def file_only_m(filepath):
	return filepath.endswith('.m');

def file_only_m_or_h(filepath):
	return filepath.endswith('.m') or filepath.endswith('.h');

def file_only_m_or_mm(filepath):
	return filepath.endswith('.m') or filepath.endswith('.mm');

def get_class_property_map(path):
	all_file = dirList_walk(path)
	all_file = filter(file_only_h,all_file)
	for filepath in all_file:
		# 不包括 分类
		file = re.findall(r'.*/(\w+)\.h',filepath)
		if len(file) == 0:
			continue
		#默认为file name
		filename = file[0]
		filecontent = open(filepath)
		
		class_name = filename
		for line in filecontent:
			# filter 注释掉的代码
			if re.match(r'( *)//',line):
				continue

			# 得到 class_name
			_a_class_name_list = re.findall(r'^@interface (\w+) ?[\:\(]',line)
			if len(_a_class_name_list) > 0:
				class_name = _a_class_name_list[0]
			# 得到 property
			_a_property_name_list = re.findall(r'^@property.*[\s\*] ?(\w+) ?;',line)
			if len(_a_property_name_list) > 0:
				property_name = _a_property_name_list[0]
				set_dic_strKey_valueList(class_property_map,class_name,property_name)

			_a_property_type_list = re.findall(r'^@property ?\(.*\) ?(\w+) ?\*? ?(\w+) ?;',line)
			if len(_a_property_type_list) > 0:
				property_type = _a_property_type_list[0][0]
				property_name = _a_property_type_list[0][1]
				_a_map = {}
				if class_property_type_map.has_key(class_name):
					_a_map = class_property_type_map[class_name]
				_a_map[property_name] = property_type
				class_property_type_map[class_name] = _a_map

		filecontent.close()

# line = '[[A hhh] kkkk];'
# line = '[[A hhh] kkkk:@"123"];'
def get_methods_on_line(line):
	result = {}
	_list = re.findall(r'\[(\w+) (\w+:?)\w*[\]\^]',line)
	if len(_list) > 0:
		clazz_or_instanzz_name = _list[0][0]
		result['clazz_or_instanzz_name'] = clazz_or_instanzz_name
		result['class_method_list'] = []

		method_name = _list[0][1]
		result.get('class_method_list').append(method_name)
		subline = re.sub(r'(\[\w+ \w+:?\w*\])', 'Tmp', line)
		_sublist = re.findall(r'\[\w+ (\w*:?).+\]',subline)
		if len(_sublist) > 0:
			method_name = _sublist[0]
			result.get('class_method_list').append(method_name)
	return result

# line = '[A a:@"123" b:1];'
def get_methods_on_line_with2Param(line):
	result = {}
	_list = re.findall(r'\[(\w+) (\w+:).* (\w+:).*[\]\{]',line)
	if len(_list) > 0:
		clazz_or_instanzz_name = _list[0][0]
		result['clazz_or_instanzz_name'] = clazz_or_instanzz_name
		result['class_method_list'] = [_list[0][1]+_list[0][2]]
	return result

# [[EventManager eventStore] saveEvents:eventsFromServer];
# [[self eventStore] saveEvents:eventsFromServer];
def get_methods_on_line_for_getter(filename,line):
	result = {}
	_list = re.findall(r'\[(\w+) (\w+)\] ?(\w+:?)\w*\]',line)
	if len(_list) == 0:
		# [self.eventStore removeAllEvents];
		_list = re.findall(r'\[(\w+)\.(\w+) (\w+:?)\w*\]',line)

	if len(_list) > 0:
		clazz_or_instanzz_name = _list[0][0]
		getter_method = _list[0][1]
		method_name = _list[0][2]

		class_name = filename
		if clazz_or_instanzz_name == 'self':
			pass
		elif define_manager_expression_map.has_key(clazz_or_instanzz_name):
			class_name = define_manager_expression_map[clazz_or_instanzz_name]

		if class_property_type_map.has_key(class_name):
			_a_property_type_map = class_property_type_map[class_name]
			if _a_property_type_map.has_key(getter_method):
				property_type = _a_property_type_map[getter_method]
				result['clazz_or_instanzz_name'] = property_type
				result['class_method_list'] = [method_name]

	return result

# #line = '[EventManager createEvent:weakSelf.event'
#[[OAEventManager sharedInstance] exportEventToSystemCalendar:self.eventInstance thenDo:^(NSError *error) {
# def get_methods_on_line_2block(line):
# 	result = {}
# 	_list = re.findall(r'\[(\w+) (\w+:).* (\w+:)\^',line)
# 	if len(_list) > 0:
# 		result['clazz_or_instanzz_name'] = _list[0][0]
# 		result['class_method_list'] = [_list[0][1]+_list[0][2]]
# 	return result

def get_uncalled_class_methods_map():
	for item in class_methods_map.items():
		class_name = item[0]
		method_list = item[1]

		called_method_list = []
		if called_class_methods_map.has_key(class_name):
			called_method_list = called_class_methods_map.get(class_name)

		for method_name in method_list:
			if method_name in called_method_list or method_name in sepcial_method_list():
				pass
			else:
				set_dic_strKey_valueList(uncalled_class_methods_map,class_name,method_name)

def confirm_uncalled_method_from_superclass():
	for item in uncalled_class_methods_map.items():
		class_name = item[0]
		uncalled_method_list = item[1]

		if subclass_fatherclass_map.has_key(class_name):
			fatherclass_name = subclass_fatherclass_map[class_name]
			
			# 判断当前uncalled_method 是否存在fatherclass的 called_method／setter/getter中
			fatherclass_called_method_list = []
			if called_class_methods_map.has_key(fatherclass_name):
				fatherclass_called_method_list = called_class_methods_map[fatherclass_name]
			if class_property_setter_getter_map.has_key(fatherclass_name):
				fatherclass_called_method_list.extend(class_property_setter_getter_map[fatherclass_name])
			if len(fatherclass_called_method_list) > 0:
				uncalled_method_list_tmp = []
				for uncalled_method in uncalled_method_list:
					if uncalled_method in fatherclass_called_method_list:
						pass
					else:
						uncalled_method_list_tmp.append(uncalled_method)
				uncalled_class_methods_map[class_name] = uncalled_method_list_tmp


def get_subclass_fatherclass_map(path):
	all_file = dirList_walk(path)
	all_file = filter(file_only_h,all_file)
	for filepath in all_file:
		# 不包括 分类
		file = re.findall(r'.*/(\w+)\.h',filepath)
		if len(file) == 0:
			continue
		#默认为file name
		filename = file[0]
		filecontent = open(filepath)
		
		class_name = filename
		for line in filecontent:
			# filter 注释掉的代码
			if re.match(r'( *)//',line):
				continue

			_a_subclass_fatherclass_list = re.findall(r'^@interface (\w+) ?: ?(\w+)',line)
			if len(_a_subclass_fatherclass_list) > 0:
				subclass_name = _a_subclass_fatherclass_list[0][0]
				fatherclass_name = _a_subclass_fatherclass_list[0][1]
				if fatherclass_name.startswith('NS') or fatherclass_name.startswith('UI'):
					continue
				else:
					subclass_fatherclass_map[subclass_name] = fatherclass_name

		filecontent.close()	

def get_define_manager_expression_map(path):
	all_file = dirList_walk(path)
	all_file = filter(file_only_h,all_file)
	for filepath in all_file:
		# 不包括 分类
		file = re.findall(r'.*/(\w+)\.[mh]',filepath)
		if len(file) == 0:
			continue
		#默认为file name
		filename = file[0]
		filecontent = open(filepath)
		
		class_name = filename
		for line in filecontent:
			# filter 注释掉的代码
			if re.match(r'( *)//',line):
				continue
			# #define EventManager [OAEventManager sharedInstance]
			_a_define_manager_expression_list = re.findall(r'^#define (\w+) \[(\w+) \w+\]',line)
			if len(_a_define_manager_expression_list) > 0:
				define_name = _a_define_manager_expression_list[0][0]
				class_name = _a_define_manager_expression_list[0][1]
				define_manager_expression_map[define_name] = class_name
		filecontent.close()	

def remove_special_class():
	global uncalled_class_methods_map

	# prefix
	sepcial_class_prefix_list = ['NS','UI','CA','BM','AMap','MA','IFly','BLY','Map','FX','IS','WX','DI','TM','PL','PN']
	sepcial_class_prefix_list.extend(['SendAuthReq','MLEmojiLabel','AudioPlayer','BuglyConfig','WechatAuthSDK','JumpToBizWebviewReq'])
	sepcial_class_prefix_list.extend(['WKWebView','IphoneGPSMan','TLAudioPlayer',])
	uncalled_class_methods_map_pre = {}
	for item in uncalled_class_methods_map.items():
		class_name = item[0]
		uncalled_method_list = item[1]
		is_sepcial = False
		for prefix in sepcial_class_prefix_list:
			if class_name.startswith(prefix):
				is_sepcial = True
		if is_sepcial == False:
			uncalled_class_methods_map_pre[class_name] = uncalled_method_list
	uncalled_class_methods_map = uncalled_class_methods_map_pre

	# third lib class name
	uncalled_class_methods_map_third_lib = {}
	for item in uncalled_class_methods_map.items():
		class_name = item[0]
		uncalled_method_list = item[1]
		if class_name in special_class_from_third_lib_list:
			pass
		else:
			uncalled_class_methods_map_third_lib[class_name] = uncalled_method_list
	uncalled_class_methods_map = uncalled_class_methods_map_third_lib


def get_special_class_from_third_lib_list(path):
	all_file = dirList_walk(path)
	all_file = filter(file_only_m_or_h,all_file)
	for filepath in all_file:
		file = re.findall(r'.*/(\w+\+?\w*)\.[mh]',filepath)
		if len(file) == 0:
			continue
		#默认为file name
		filename = file[0]
		filecontent = open(filepath)
		
		class_name = filename
		for line in filecontent:
			# filter 注释掉的代码
			if re.match(r'( *)//',line):
				continue
			# @interface AFHTTPSessionManager : AFURLSessionManager <NSSecureCoding, NSCopying>
			_a_class_name_list = re.findall(r'^@interface (\w+) :',line)
			if len(_a_class_name_list) > 0:
				
				class_name = _a_class_name_list[0]
				if class_name in special_class_from_third_lib_list:
					pass
				else:
					special_class_from_third_lib_list.append(class_name)

		filecontent.close()	

def sepcial_method_list():
	sepcial_method = ['.cxx_destruct','.cxx_construct']
	sepcial_method.extend(['onNewMqttContent:withAction:'])
	sepcial_method.extend(['load','awakeFromNib','layoutSubviews','viewDidLoad','viewWillLayoutSubviews','viewWillAppear:','viewWillDisappear:','dealloc','didReceiveMemoryWarning','initWithNibName:bundle:','initWithFrame:'])
	sepcial_method.extend(['application:didFinishLaunchingWithOptions:', 'applicationWillResignActive:', 'applicationDidEnterBackground:', 'applicationWillEnterForeground:', 'applicationDidBecomeActive:', 'applicationWillTerminate:'])
	sepcial_method.extend(['initWithCoder:','copyWithZone:','copy','mutableCopy', 'isEqual:', 'hash', 'description'])
	sepcial_method.extend(['textFieldShouldBeginEditing:', 'textFieldDidBeginEditing:','textFieldShouldEndEditing:','textField:shouldChangeCharactersInRange:replacementString:', 'textViewDidChange:', 'textViewShouldBeginEditing:'])
	sepcial_method.extend(['becomeFirstResponder','resignFirstResponder','canBecomeFirstResponder', 'canResignFirstResponder'])
	sepcial_method.extend(['numberOfComponentsInPickerView:', 'pickerView:numberOfRowsInComponent:', 'pickerView:titleForRow:forComponent:', 'pickerView:didSelectRow:inComponent:'])
	sepcial_method.extend(['tableView:didSelectCell:rowAtIndexPath:', 'tableView:heightForCell:rowAtIndexPath:','tableView:cellForRowAtIndexPath:', 'tableView:numberOfRowsInSection:', 'tableView:cellForItem:rowAtIndexpath:', 'tableView:decorateCell:forItem:atIndexpath:', 'tableView:heightForItem:rowAtIndexPath:','tableView:shouldHighlightRowAtIndexPath:','tableView:willDisplayCell:forRowAtIndexPath:','tableView:heightForHeaderInSection:','tableView:didSelectItem:rowAtIndexPath:'])
	sepcial_method.extend(['scrollViewDidScroll:','scrollViewDidEndDragging:willDecelerate:','scrollViewWillEndDragging:withVelocity:targetContentOffset:'])
	sepcial_method.extend(['searchBar:textDidChange:', 'searchBarTextDidBeginEditing:', 'searchBarCancelButtonClicked:', 'searchBarSearchButtonClicked:', 'numberOfSectionsInTableView:', 'tableView:viewForHeaderInSection:', 'tableView:heightForFooterInSection:', 'tableView:heightForRowAtIndexPath:', 'tableView:didSelectRowAtIndexPath:'])
	sepcial_method.extend(['listView:numberOfRowsInSection:', 'listView:imageUrlAtIndex:', 'listView:defaultImageAtIndex:', 'listView:fileAtIndex:', 'listView:didTapPhotoAtIndex:', 'listView:didTapFileAtIndex:','listView:didDeleteFileAtIndex:'])
	sepcial_method.extend(['numberOfSectionsInCollectionView:', 'collectionView:numberOfItemsInSection:', 'collectionView:viewForSupplementaryElementOfKind:atIndexPath:', 'collectionView:cellForItemAtIndexPath:', 'collectionView:layout:referenceSizeForHeaderInSection:', 'collectionView:layout:sizeForItemAtIndexPath:'])
	return sepcial_method

# 脚本使用说明：
# python ios.py linkmap_path project_path pod_path >> ios.txt
# 举个例子：python ios.py '/Users/wangdt/python/linkMap.txt' '/Users/wangdt/WBG/3.2/oa' '/Users/wangdt/WBG/3.2/Pods/' >> ios.txt

# 参数说明
# 0: ios.py,	【必填】脚本的路径
# 1: linkmap_path，	【必填】项目编译后生成的linkmap文件的路径（你可以复制出来，方便调试）
# 2: project_path，	【必填】项目的根路径，用来遍历你的整个项目（你可以选择某个文件夹）
# 3: pod_path，	【选填】用来统计第三方库中的class_name_list，过滤掉uncalled_method

if len(sys.argv) >= 3:
	linkmap_path = sys.argv[1] 
	project_path = sys.argv[2] 
	if len(sys.argv) == 4:
		pod_path = sys.argv[3]
		
	# linkmap_path = '/Users/wangdt/python/linkMap.txt' #linkMap的位置
	# project_path = '/Users/wangdt/WBG/3.2/oa' # 项目代码的位置
	# pod_path = '/Users/wangdt/WBG/3.2/Pods/' # 用来统计第三方库中的class_name_list，过滤掉 uncalled_method

	get_define_manager_expression_map(project_path)
	get_subclass_fatherclass_map(project_path)

	get_class_property_map(project_path) # .h文件中的 property:部分IVAR+ s(g)etter
	get_class_ivar_map(linkmap_path) # IVAR
	get_class_property_setter_getter_map()
	get_class_methods_map(linkmap_path)

	get_called_class_methods_map(project_path)
	get_uncalled_class_methods_map()
	confirm_uncalled_method_from_superclass()

	get_special_class_from_third_lib_list(pod_path) 
	remove_special_class() # 过滤掉第三库库的methods

	print 'uncalled_class_methods_map 未被调用的方法：'
	for item in uncalled_class_methods_map.items():
		if len(item[1]) > 0:
			print "-----------------------------------"
			print item[0]
			print item[1]

# 测试某个具体的类时，可以用下面这个方法
def test_only_class(filter_name):
	print 'class_methods_map 所有的方法：'
	for item in class_methods_map.items():
		if item[0] == filter_name:
			if len(item[1]) > 0:
				print item[1]

	print ' '
	print 'called_class_methods_map 被调用过的方法：'
	for item in called_class_methods_map.items():
		if item[0] == filter_name:
			if len(item[1]) > 0:
				print item[1]

	print ' '
	print 'class_property_setter_getter_map setter/getter方法：'
	for item in class_property_setter_getter_map.items():
		if item[0] == filter_name:
			if len(item[1]) > 0:
				print item[1]

	print ' '
	print 'class_property_map 类的属性：'
	for item in class_property_map.items():
		if item[0] == filter_name:
			if len(item[1]) > 0:
				print item[1]
	
	print ' '
	print 'class_property_type_map 类的属性 类型：'
	for item in class_property_type_map.items():
		if item[0] == filter_name:
			if len(item[1]) > 0:
				print item[1]
	
	print ' '
	print 'uncalled_class_methods_map 未被调用的方法：'
	for item in uncalled_class_methods_map.items():
		if item[0] == filter_name:
			if len(item[1]) > 0:
				print item[1]




