import requests
import streamlit as st
from config import config
import plotly.graph_objects as go
import os
import json
import copy
import pandas as pd

# 角色列表
role_keys = config["role"].keys()
# 端口
port = config['port']
url = f"http://0.0.0.0:{port}/"

st.set_page_config(page_title="RWKV Chatting", page_icon="🏠")
st.title('RWKV-Ouroboros')
st.write("""
         RWKV-Ouroboros是一个基于RWKV的在线推理与在线训练的框架。其核心理念是’人在回路‘。  
         项目地址:[RWKV-Ouroboros](https://github.com/neromous/RWKV-Ouroboros)
         """)

mode = st.toggle('推理模式/训练模式', value=False)

if mode:
# ================
# Train Mode
# ================
    with st.sidebar:
        st.title("Training Settings")

        train_mode = st.radio(label="选择训练模式", options=["tx-data(推荐)","tokens(测试中)"],captions=["将多个text拼接后，定长训练","接收分词后token_id的整数列表，加快计算"], horizontal=True,key="train_mode")
        if train_mode == "tx-data(推荐)":
            route = "/trainer/by/tx-data"
        elif train_mode == "tokens(测试中)":
            route = "/trainer/by/tokens"

        with st.container(border = True):
            col11, col22 = st.columns(2)
            with col11:
                max_loss = st.number_input(label="max_loss", value = config['trainer']["max_loss"], key="max_loss")
                min_loss = st.number_input(label="min_loss", value= config['trainer']["min_loss"], key="min_loss")
                min_loss_fix = st.number_input(label="min_loss_fix", value=config['trainer']["min_loss_fix"], key="min_loss_fix")
            with col22:
                max_loss_fix = st.number_input(label="max_loss_fix", value=config['trainer']["max_loss_fix"], key="max_loss_fix")
                ctx_len = st.number_input(label="ctx_len", value=config['model']["ctx_len"], key="ctx_len")
                window = st.number_input(label="window", value=config['trainer']["window"], key="window")

    st.caption(f"当前为：训练模式")

    # --------------- 1.训练数据 -------------------
    with st.container(border = True):
        st.subheader("1.训练数据")
        # 选择训练数据上传方式
        data_mode = st.selectbox(label="数据上传方式",index=1, options=["拖拽文件", "手动编辑数据"],key="data_mode")
        with st.expander("示例数据格式", expanded=False):
            st.caption("说明：数据格式应该为jsonl文件，其中每一条json数据对应一个角色的发言：包括role和text两个字段。")
            json_examp = [{"role": "system", "text": "你是一个乐于助人的AI。"},
                        {"role": "request", "text": "你好"},
                        {"role": "response", "text": "我很好，你呢"},
                        {"role": "request", "text": "你叫什么名字"},
                        {"role": "response", "text": "我叫伊芙"},]
            st.write(json_examp)

        if data_mode == "拖拽文件":
            # 上传jsonl文件
            uploaded_file =  st.file_uploader(label="上传训练数据", type=["jsonl"], key="tx_data")
            if uploaded_file:
                # 预览训练数据
                stringio = uploaded_file.getvalue().decode("utf-8")
                data = stringio.split("\n")  # 按行分割
                json_data = [json.loads(x) for x in data if x]  # 转换为json，并排除空行
                st.success("读取成功")
                with st.expander("预览数据", expanded=False):
                    st.write(json_data)
            else:
                # 以示例数据json_list为默认值
                json_data = json_examp
                st.caption("文件未上传，默认使用示例数据")

            tx_data = { "max_loss": max_loss,
                        "min_loss": min_loss,
                        "min_loss_fix": min_loss_fix,
                        "max_loss_fix": max_loss_fix,
                        "ctx_len": ctx_len,
                        "window": window,
                        "messages":json_data,
                        }

        elif data_mode == "手动编辑数据":
            # 新建一个空的可编辑的数据表格
            df = pd.DataFrame(columns=["role","text"])
            # 添加一行空数据
            df.loc[0] = ["system",""]
            st.write("双击编辑数据:")
            # 显示数据表格
            edited_df = st.data_editor(df, 
                                        num_rows="dynamic", 
                                        key="tx_data",
                                        use_container_width=True,
                                        hide_index=False,
                                        column_config={
                                            "_index": st.column_config.NumberColumn(
                                                "index",
                                                help="请确保此列为不同的整数",
                                                default=None,
                                                required=True,
                                                width="small",
                                                ),
                                            "role": st.column_config.SelectboxColumn(
                                                help="从config.py中定义的role中选择",
                                                width="medium",
                                                default=None,
                                                options=role_keys,
                                                required=True,
                                                ),
                                            "text": st.column_config.TextColumn(
                                                help="请手动输入训练数据",
                                                width="large",
                                                default=None,
                                                required=True,
                                                ),
                                            },
                                         )
            st.caption("""说明：  
1、用户可以增删row，来控制对话的轮数。  
2、可以自选角色（自定义角色需要编辑config.py）  
3、务必保证每一行的index为**不同的整数**，否则数据会丢失。  
4、表格可全屏显示，方便编辑。
                       """)
            # 删除edited_df中的空行，并将每一行转换为json，所有行合并一个list格式,utf-8格式
            json_data = edited_df.dropna(how='all').to_json(orient="records", force_ascii=False)
            json_list = json.loads(json_data)
            with st.expander("预览数据", expanded=True):
                st.write(json_list)

            train_data_dir = st.text_input(label="输入保存数据的名称：", placeholder ="例如log1", key="save_data_dir")
            if st.button("备份数据", help="将当前编辑的数据保存为jsonl文件,默认路径为'./resources/train_data/'"):
                # 检查路径是否存在
                if not os.path.exists("./resources/train_data"):
                    # 如果不存在，则创建新的文件夹
                    os.makedirs("./resources/train_data")
                # 将st.session_state中的对话记录以jsonl格式保存
                with open(f"./resources/train_data/{train_data_dir}.jsonl", 'w', encoding='utf-8') as f:
                    f.write(json_data)
                st.success("保存成功")
            
            tx_data = { "max_loss": max_loss,
            "min_loss": min_loss,
            "min_loss_fix": min_loss_fix,
            "max_loss_fix": max_loss_fix,
            "ctx_len": ctx_len,
            "window": window,
            "messages":json_list,
            }

            # col_A, col_B = st.columns(2)
            # with col_A:
            #     role1 = st.selectbox(label="角色1", options=role_keys, key="role1")
            #     message1 = st.text_input(label="角色1对话",placeholder="输入训练数据", key="message")
            # with col_B:
            #     role2 = st.selectbox(label="角色2", options=role_keys, key="role2")
            #     message2 = st.text_input(label="角色2对话",placeholder="输入训练数据", key="message2")

            # tx_data = { "max_loss": max_loss,
            #             "min_loss": min_loss,
            #             "min_loss_fix": min_loss_fix,
            #             "max_loss_fix": max_loss_fix,
            #             "ctx_len": ctx_len,
            #             "window": window,
            #             "messages":[
            #                     {"role":role1,
            #                     "text":f"{message1}",
            #                     "prefix":"",
            #                     "postfix":"",
            #                     "prefix_token":config["role"][role1]["prefix"],
            #                     "postfix_token":config["role"][role1]["postfix"],
            #                     "response":"",
            #                     "over": True,
            #                     "no_loss": False,
            #                     "mask": 1.0,
            #                     "role_mask": 1.0,
            #                     },

            #                     {"role":role2,
            #                     "text":f"{message2}",
            #                     "prefix":"",
            #                     "postfix":"",
            #                     "prefix_token":config["role"][role2]["prefix"],
            #                     "postfix_token":config["role"][role2]["postfix"],
            #                     "response":"",
            #                     "over": True,
            #                     "no_loss": False,
            #                     "mask": 1.0,
            #                     "role_mask": 1.0,
            #                     },
            #                     ],
            #             }

    # --------------- 2.训练效果 -------------------
    with st.container(border = True):
        st.subheader("2. 训练效果")
        if "losses" not in st.session_state:
            st.session_state["losses"] = []

        # 初始化Plotly图表
        fig = go.Figure()
        # 检查是否已有数据
        fig.add_trace(go.Scatter(
            x=list(range(1, max(len(st.session_state["losses"]) + 1,3))),
            y=st.session_state["losses"],
            mode='lines+markers',  # 线条+标记
            name='Loss'
        ))
        fig.update_layout(title='Loss损失函数',
                        xaxis_title='训练次数',
                        yaxis_title='Loss')
        chart = st.plotly_chart(fig, use_container_width=True)

        col_1, col_2= st.columns([4,1])
        with col_1:
            my_bar = st.progress(0, text="训练进度")
        with col_2:
            if st.button('清空loss绘图'):
                st.session_state["losses"] = []
                st.rerun()

        # 训练次数
        col_A,col_B = st.columns(2)
        with col_A:
            iter = st.number_input(label="训练次数", value=3, placeholder="请输入训练次数",key="iter")
            if st.button('开始训练'):
                with st.spinner('Training...'):
                    for i in range(iter):
                        r = requests.post(url + route, json=tx_data)
                        if r.status_code == 200:
                            loss = r.json().get("loss")
                            st.session_state["losses"].append(loss)
                            # 更新图表数据
                            fig.data[0].x = list(range(1, len(st.session_state["losses"]) + 1))
                            fig.data[0].y = st.session_state["losses"]
                            # 重新绘制图表
                            chart.plotly_chart(fig, use_container_width=True)

                        else:
                            st.error(f"第{i+1}次迭代训练失败,结果如下：")
                            st.write(f"服务器返回状态码：{r.status_code}")
                            st.write(r.text)
                            break
                        # 更新进度条
                        my_bar.progress((i+1)/iter, text=f"training...{i+1}/{iter}， loss: {(loss):.4f}")
                st.success(f"训练完成")
        with col_B:
            save_model_dir = st.text_input(label="输入保存模型的名称：", placeholder ="例如default", key="save_model_dir")
            if st.button('保存model', help="默认路径为'./resources/weights/**.pth'"):
                r = requests.post(url+"/trainer/model/save-to-disk",json={"save_name" : f"{save_model_dir}"})
                if r.status_code == 200:
                    r = r.json()
                    if r.get("message"):
                        st.success(f"{r['message']}")
                    else:
                        st.error("保存模型失败,结果如下：")
                        st.write(r)
                else:
                    st.error(f"保存模型失败,服务器状态码：{r.status_code}")

# ================
# Infer Mode
# ================
elif not mode:
    st.caption(f"当前为：推理模式")
    # with st.expander("Inference Settings", expanded=True):
    with st.sidebar:
        st.title("Inference Settings")
        infer_mode = st.selectbox(label="**选择推理模式：**", options=["tx-data(推荐)","tokens(测试中)"], key="infer_mode")
        with st.container(border = True):
            col1, col2 = st.columns(2)
            with col1:
                temperature = st.number_input(label="temperature", value=0.1, key="temperature", help="温度越高，生成的文本越随机；温度越低，生成的文本越固定；为0则始终输出相同的内容。")
                token_count = st.number_input(label="token_count", value=256, key="token_count")
                token_ban = st.number_input(label="token_ban", value=None, key="token_ban", help="token_ban:使模型避免输出该token。")
                token_stop = st.number_input(label="token_stop", value = None, key="token_stop", help="token_stop:使模型停止输出的token。")
            with col2:
                top_p = st.number_input(label="top_p", value=0.85, key="top_p", help="top_p越高，生成的文本越多样。")
                alpha_presence = st.number_input(label="存在惩罚", value=0.2, key="alpha_presence", help="alpha_presence:正值鼓励主题多样，负值鼓励主题一致。")
                alpha_frequency = st.number_input(label="频率惩罚", value=0.2, key="alpha_frequency", help="alpha_frequency:正值避免重复内容，负值鼓励重复内容。")
                alpha_decay = st.number_input(label="惩罚衰减", value=0.996, key="alpha_decay", help="alpha_decay:惩罚力度衰减系数。")

            debug = st.checkbox(label="debug模式", value=False,help="是否在终端打印state变化", key="debug")
        
        if infer_mode == "tx-data(推荐)":
            route = "/inference/tx-data"
        # elif infer_mode == "messages":
        #     route = "/inference/by/messages"
        elif infer_mode == "tokens(测试中)":
            route = "/inference/by/tokens"

# ================
# State Process
# ================
with st.expander("高级设置(State 处理)", expanded=False):
    if config["trainer"]["infctx_on"]:
        st.caption("已开启infctx模式")
    else:
        st.caption("未开启infctx模式,不能处理train state")

    # 如果是训练模式，就是trainer的state处理，
    if mode:
        reset_route = "/trainer/state/reset"
        save_route = "/trainer/state/save"
        load_route = "/trainer/state/load"
        to_disk_route = "/trainer/state/save-to-disk"

    # 否则是inference的state处理
    else:
        reset_route = "/inference/state/reset"
        save_route = "/inference/state/save"
        load_route = "/inference/state/load"
        to_disk_route = "/inference/state/save-to-disk"

    if st.button('Reset State',help="清空state为初始状态(根据train/infer模式自动选择train state/infer state)"):
        r = requests.post(url+reset_route,json={"messages" : ""})
        if r.status_code == 200:
            r = r.json()
            if r.get("message"):
                st.success(f"{r['message']}")
            else:
                st.error("重置train state失败,结果如下：")
                st.write(r)

    col_a, col_b,col_c = st.columns(3)
    with col_a:
        save_state_name = st.text_input("存储state到内存", placeholder="请输入state名称", key="save_state_name")
        st.session_state.setdefault("state_names", [])

        if st.button("Save State", help="将当前模型的state暂时保存到内存"):
            if save_state_name and save_state_name not in st.session_state["state_names"]:
                r = requests.post(url + save_route, json={"save_state": save_state_name})

                if r.status_code == 200 :
                    r = r.json()
                    message = r.get("message")
                    if message == "success":
                        st.success(f"保存state成功")
                        st.session_state["state_names"].append(save_state_name)
                    else:
                        st.error(f"保存state失败,请确保state不为初始化状态")
                else:
                    st.error(f"服务器返回状态码 {r.status_code}")
            else:
                st.error("保存train state失败：名称不能为空或已存在")

    with col_b:
        load_state_name = st.selectbox("加载内存中的state", options=st.session_state["state_names"], key="load_state_dir")
        if st.button('Load State'):
            r = requests.post(url+load_route,json={"load_state" : f"{load_state_name}"})
            r = r.json()
            if r.get("message"):
                st.success(f"{r['message']}")
            else:
                st.error("加载train state失败,结果如下：")
                st.write(r)
    
    with col_c:
        save_state_dir = st.text_input("存储state到硬盘", placeholder="请输入state名称", key="save_state_dir")
        if st.button('Save State to Disk',help="默认保存State到’./resources/states_for_infer/"):
            r = requests.post(url+to_disk_route,json={"save_state" : f"{save_state_dir}"})


# ===============聊天界面==================
# 推理模式
if not mode:

    a, b, c, = st.columns([4,1,1])
    with b:
        if st.button("清空对话", help="清空对话记录并重置state为初始状态"):
            st.session_state["messages"] = []
            r = requests.post(url+reset_route,json={"messages" : ""})
            st.rerun()
    with c:
        if st.button("保存对话", help="将对话记录保存为jsonl,默认路径为‘./resources/dialogues/’"):
            # 检查路径是否存在
            if not os.path.exists("./resources/dialogues"):
                # 如果不存在，则创建新的文件夹
                os.makedirs("./resources/dialogues")
            # 将st.session_state中的对话记录以jsonl格式保存
            with open("./resources/dialogues/log1.jsonl", 'w', encoding='utf-8') as f:
                for message in st.session_state.messages:
                    # 创建一个新的字典来存储修改后的信息
                    new_message = copy.deepcopy(message)
                    # 在新的字典中重命名 'content' 为 'text'
                    new_message['text'] = new_message.pop('content')
                    json_record = json.dumps(new_message, ensure_ascii=False)
                    f.write(json_record + '\n')
            st.success("保存成功")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Ask something"):

        data={"messages" : [{"role":"question",
                            "text":f"{prompt}",
                            "over": True,
                            "token_count":0,
                            "token_stop": None,
                            },
                            
                            {"role":"answer",
                            "text":"",
                            "over": False,
                            "token_stop": [261],
                            "token_count": token_count,
                            "temperature": temperature,
                            "top_p":top_p,
                            "alpha_frequency":alpha_frequency,
                            "alpha_presence":alpha_presence,
                            "alpha_decay":alpha_decay,
                            },
                            ],
                "debug" : debug,}
        
        roles= ["human","assistant","system"]
        st.session_state.messages.append({"role": roles[0], "content":prompt})
        st.chat_message(roles[0]).write(prompt)

        # 模型的反馈结果
        r = requests.post(url + route,json = data)
        response = r.json()
        answer = response["messages"][1]["response"]


        # 双角色对话
        st.chat_message(roles[1]).write(response["messages"][1]["response"])
        st.session_state.messages.append({"role":roles[1],"content":response["messages"][1]["response"]})
        # st.chat_message(roles[2]).write(response)
        # st.session_state.messages.append({"role":roles[2],"content":response})

        #
        #     # 多角色对话
        #     dialogue = response["messages"][1]["response"]
        #     lines = dialogue.strip().split("\n\n")
        #     lines = [line for line in lines if line.strip() != ""]

        #     for line in lines:
        #         role = "assistant"
        #         line = line.lstrip("<|me|>").rstrip("<|over|>")
        #         parts = line.rsplit("|>",1)
        #         if len(parts) == 2:
        #             pre_text = parts[0].strip()
        #             answer = parts[1].strip()
        #             for key in role_keys:
        #                 if key in pre_text:
        #                     role = key
        #                     break
        #             st.chat_message(role).write(f"||{role}||  " + answer)
        #             st.session_state.messages.append({"role":role,"content":f"||{role}||  "+answer})
        #         else:
        #             for key in role_keys:
        #                 if key in line[0:10]:
        #                     role = key
        #             st.chat_message(role).write(line)
        #             st.session_state.messages.append({"role":role,"content":line})


            