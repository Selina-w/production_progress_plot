import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from datetime import datetime, timedelta
import matplotlib.font_manager as fm
import io
import tempfile
import os
import zipfile
import matplotlib as mpl

plt.rcParams['font.sans-serif'] = ['PingFang HK', 'Songti SC', 'Arial Unicode MS']
#plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False  # Fix minus signs
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['path.simplify'] = False  # Don't simplify paths for better quality
plt.rcParams['agg.path.chunksize'] = 10000  # Increase path chunk size
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['figure.edgecolor'] = 'white'
plt.rcParams['lines.antialiased'] = True
plt.rcParams['patch.antialiased'] = True
plt.rcParams['text.antialiased'] = True
plt.rcParams['text.hinting'] = 'auto'  # Better text rendering
plt.rcParams['text.hinting_factor'] = 8  # Sharper text
plt.rcParams['text.usetex'] = False  # Disable LaTeX by default
plt.style.use('default')  # Reset to default style for clean rendering

# 检查字体是否可用
font_names = [f.name for f in fm.fontManager.ttflist]
chinese_fonts = [f for f in font_names if any(name in f for name in ['PingFang', 'Microsoft', 'SimHei', 'Arial Unicode'])]
if chinese_fonts:
    plt.rcParams['font.sans-serif'] = chinese_fonts[0]
    print(chinese_fonts[0])

# 部门工序定义
def get_department_steps(process_type=None):
    """Get department steps based on process type"""
    all_departments = {
        "面料": ["排版", "用料", "棉纱", "毛坯", "色样发送", "色样确认", "光坯", "物理检测+验布"],
        "印布": ["印布样品发送", "印布确认", "印布工艺", "印布", "印布后整", "物理检测"],
        "裁剪1": ["产前样发送", "产前样确认", "工艺样版", "裁剪"],
        "印花": ["印花样品确认", "印花确认", "印花工艺", "印花", "物理检测"],
        "绣花": ["绣花样品确认", "绣花确认", "绣花工艺", "绣花", "物理检测"],
        "裁剪2": ["配片"],
        "裁片库": ["滚领布"],
        "辅料": ["辅料样发送", "辅料确认", "辅料限额", "辅料", "物理检测"],
        "缝纫": ["缝纫工艺", "缝纫开始"]
    }
    
    if process_type is None:
        return all_departments
        
    # Filter departments based on process type
    if process_type == "满花+局花":
        # Exclude 绣花 department
        return {k: v for k, v in all_departments.items() if k != "绣花"}
    elif process_type == "满花+绣花":
        # Exclude 印花 department
        return {k: v for k, v in all_departments.items() if k != "印花"}
    elif process_type == "局花+绣花":
        # Exclude 印布 department
        return {k: v for k, v in all_departments.items() if k != "印布"}
    else:  # "满花+局花+绣花"
        return all_departments

def calculate_schedule(sewing_start_date, process_type, confirmation_period):
    """ 计算整个生产流程的时间安排 """
    schedule = {}
    
    # 将所有工序的时间初始化为字典
    for dept, steps in get_department_steps(process_type).items():
        schedule[dept] = {}
    
    X = sewing_start_date  # 预计缝纫开始日期

    # 1. 计算面料阶段
    if process_type == "满花+局花+绣花":
        offset = 41
    elif process_type in ["满花+局花", "局花+绣花"]:
        offset = 35
    elif process_type == "满花+绣花":
        offset = 37
    
    schedule["面料"]["排版"] = {"时间点": X - timedelta(days=offset)}
    schedule["面料"]["用料"] = {"时间点": X - timedelta(days=offset)}
    schedule["面料"]["棉纱"] = {"时间点": X - timedelta(days=offset-3)}
    schedule["面料"]["毛坯"] = {"时间点": X - timedelta(days=offset-7)}
    
    # 2. 计算色样流程
    schedule["面料"]["色样确认"] = {"时间点": schedule["面料"]["毛坯"]["时间点"]}
    schedule["面料"]["色样发送"] = {"时间点": schedule["面料"]["色样确认"]["时间点"] - timedelta(days=confirmation_period)}

    # 3. 计算光胚之后的流程
    schedule["面料"]["光坯"] = {"时间点": schedule["面料"]["色样确认"]["时间点"] + timedelta(days=5)}
    schedule["面料"]["物理检测+验布"] = {"时间点": schedule["面料"]["光坯"]["时间点"] + timedelta(days=1)}

    # 4. 计算印布流程
    if "印布" in schedule:
        schedule["印布"]["印布确认"] = {"时间点": schedule["面料"]["物理检测+验布"]["时间点"]}
        schedule["印布"]["印布样品发送"] = {"时间点": schedule["印布"]["印布确认"]["时间点"] - timedelta(days=confirmation_period)}
        schedule["印布"]["印布工艺"] = {"时间点": schedule["印布"]["印布确认"]["时间点"] + timedelta(days=1)}
        schedule["印布"]["印布"] = {"时间点": schedule["印布"]["印布工艺"]["时间点"] + timedelta(days=3)}
        schedule["印布"]["印布后整"] = {"时间点": schedule["印布"]["印布"]["时间点"] + timedelta(days=1)}
        schedule["印布"]["物理检测"] = {"时间点": schedule["印布"]["印布后整"]["时间点"] + timedelta(days=1)}

    # 5. 计算裁剪1流程
    if process_type == "局花+绣花":
        schedule["裁剪1"]["产前样确认"] = {"时间点": schedule["面料"]["光坯"]["时间点"]}
    else:
        schedule["裁剪1"]["产前样确认"] = {"时间点": schedule["印布"]["印布后整"]["时间点"]}
    schedule["裁剪1"]["产前样发送"] = {"时间点": schedule["裁剪1"]["产前样确认"]["时间点"] - timedelta(days=confirmation_period)}
    schedule["裁剪1"]["工艺样版"] = {"时间点": schedule["裁剪1"]["产前样确认"]["时间点"] + timedelta(days=1)}
    schedule["裁剪1"]["裁剪"] = {"时间点": schedule["裁剪1"]["工艺样版"]["时间点"] + timedelta(days=3)}

    # 7. 计算印花流程
    if "印花" in schedule:
        schedule["印花"]["印花确认"] = {"时间点": schedule["裁剪1"]["裁剪"]["时间点"] - timedelta(days=1)}
        schedule["印花"]["印花样品确认"] = {"时间点": schedule["印花"]["印花确认"]["时间点"] - timedelta(days=confirmation_period)}
        schedule["印花"]["印花工艺"] = {"时间点": schedule["裁剪1"]["裁剪"]["时间点"]}
        schedule["印花"]["印花"] = {"时间点": schedule["印花"]["印花工艺"]["时间点"] + timedelta(days=3)}
        schedule["印花"]["物理检测"] = {"时间点": schedule["印花"]["印花"]["时间点"] + timedelta(days=1)}

    # 8. 计算绣花流程
    if "绣花" in schedule:
        if process_type == "满花+绣花":
            schedule["绣花"]["绣花确认"] = {"时间点": schedule["裁剪1"]["裁剪"]["时间点"]- timedelta(days=1)}
        else:
            schedule["绣花"]["绣花确认"] = {"时间点": schedule["印花"]["印花"]["时间点"]}
        schedule["绣花"]["绣花样品确认"] = {"时间点": schedule["绣花"]["绣花确认"]["时间点"] - timedelta(days=confirmation_period)}
        schedule["绣花"]["绣花工艺"] = {"时间点": schedule["绣花"]["绣花确认"]["时间点"] + timedelta(days=1)}
        schedule["绣花"]["绣花"] = {"时间点": schedule["绣花"]["绣花工艺"]["时间点"] + timedelta(days=5)}
        schedule["绣花"]["物理检测"] = {"时间点": schedule["绣花"]["绣花"]["时间点"] + timedelta(days=1)}

    # 9. 计算裁剪2
    if process_type == "满花+局花":
        schedule["裁剪2"]["配片"] = {"时间点": schedule["印花"]["物理检测"]["时间点"] + timedelta(days=1)}
    else:
        schedule["裁剪2"]["配片"] = {"时间点": schedule["绣花"]["物理检测"]["时间点"] + timedelta(days=1)}

    # 10. 计算裁片库
    schedule["裁片库"]["滚领布"] = {"时间点": schedule["裁剪2"]["配片"]["时间点"]}

    # 11. 计算辅料流程（并行）
    schedule["辅料"]["辅料确认"] = {"时间点": X - timedelta(days=25)}
    schedule["辅料"]["辅料样发送"] = {"时间点": schedule["辅料"]["辅料确认"]["时间点"] - timedelta(days=confirmation_period)}
    schedule["辅料"]["辅料限额"] = {"时间点": schedule["辅料"]["辅料确认"]["时间点"] + timedelta(days=1)}
    schedule["辅料"]["辅料"] = {"时间点": schedule["辅料"]["辅料限额"]["时间点"] + timedelta(days=15)}
    schedule["辅料"]["物理检测"] = {"时间点": schedule["辅料"]["辅料"]["时间点"] + timedelta(days=1)}

    # 12. 计算缝纫工艺
    if schedule["裁片库"]["滚领布"]["时间点"] == schedule["辅料"]["物理检测"]["时间点"]:
        schedule["缝纫"]["缝纫工艺"] = {"时间点": schedule["裁片库"]["滚领布"]["时间点"] + timedelta(days=7)}
        schedule["缝纫"]["缝纫开始"] = {"时间点": schedule["缝纫"]["缝纫工艺"]["时间点"] + timedelta(days=1)}
    else:
        schedule["缝纫"]["缝纫工艺"] = {"时间点": datetime(2099, 1, 1)}
        schedule["缝纫"]["缝纫开始"] = {"时间点": datetime(2099, 1, 1)}

    return schedule

# 画时间线
def plot_timeline(schedule, process_type, confirmation_period):
    # 根据工序类型定义部门顺序和颜色
    if process_type == "满花+局花":
        department_order = ["辅料", "裁片库", "裁剪2", "印花", "裁剪1", "印布", "面料"]
        department_colors = {
            "面料": "#FFDDC1", 
            "印布": "#C1E1FF", 
            "裁剪1": "#D1FFC1", 
            "印花": "#FFC1E1", 
            "裁剪2": "#FFD1C1", 
            "裁片库": "#C1FFD1", 
            "辅料": "#E1FFC1", 
            "缝纫": "#FFC1C1"
        }
    elif process_type == "满花+绣花":
        department_order = ["辅料", "裁片库", "裁剪2", "绣花", "裁剪1", "印布", "面料"]
        department_colors = {
            "面料": "#FFDDC1", 
            "印布": "#C1E1FF", 
            "裁剪1": "#D1FFC1", 
            "绣花": "#E1C1FF", 
            "裁剪2": "#FFD1C1", 
            "裁片库": "#C1FFD1", 
            "辅料": "#E1FFC1", 
            "缝纫": "#FFC1C1"
        }
    elif process_type == "局花+绣花":
        department_order = ["辅料", "裁片库", "裁剪2", "绣花", "印花", "裁剪1", "面料"]
        department_colors = {
            "面料": "#FFDDC1", 
            "裁剪1": "#D1FFC1", 
            "绣花": "#E1C1FF", 
            "印花": "#FFC1E1", 
            "裁剪2": "#FFD1C1", 
            "裁片库": "#C1FFD1", 
            "辅料": "#E1FFC1", 
            "缝纫": "#FFC1C1"
        }
    else:  # "满花+局花+绣花"
        department_order = ["辅料", "裁片库", "裁剪2", "绣花", "印花", "裁剪1", "印布", "面料"]
        department_colors = {
            "面料": "#FFDDC1", 
            "印布": "#C1E1FF", 
            "裁剪1": "#D1FFC1", 
            "印花": "#FFC1E1", 
            "绣花": "#E1C1FF", 
            "裁剪2": "#FFD1C1", 
            "裁片库": "#C1FFD1", 
            "辅料": "#E1FFC1", 
            "缝纫": "#FFC1C1"
        }
    
    # 计算时间范围（不包括缝纫部分）
    min_date = min(times["时间点"] for dept in schedule for times in schedule[dept].values())
    max_date = max(times["时间点"] for dept in department_order for times in schedule[dept].values())
    date_range = (max_date - min_date).days
    
    # Calculate figure size and DPI based on date range
    base_width = int(date_range/41*40)  # Base width calculation
    if base_width > 24:  # If the figure is larger than default
        dpi_scale = base_width / 24  # Calculate how much larger it is
        plt.rcParams['figure.dpi'] = int(300 * dpi_scale)  # Scale DPI proportionally
        plt.rcParams['savefig.dpi'] = int(300 * dpi_scale)
    
    # Create figure with dynamic sizing and high-quality settings
    fig, ax = plt.subplots(figsize=(base_width, 16))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Enable high-quality rendering
    ax.set_rasterization_zorder(1)
    plt.rcParams['svg.fonttype'] = 'none'  # Prevent text conversion to paths
    
    # 设置y轴位置，增加行间距
    y_positions = {dept: idx * 1.5 for idx, dept in enumerate(department_order, start=1)}
    
    # 设置主时间线的起始和结束位置（留出两端的空间）
    timeline_start = 0.02  # 2% margin from left
    fixed_end = 0.89      # 固定最晚时间点的位置
    timeline_width = fixed_end - timeline_start
    
    # 绘制主要部门
    for dept in department_order:
        y = y_positions[dept]
        steps = schedule[dept]
        step_names = list(steps.keys())
        step_dates = [steps[step]["时间点"] for step in step_names]
        
        # 创建部门背景 - 从0到0.91（保持原来的位置）
        ax.fill_betweenx([y - 0.4, y + 0.4], 0, 0.91, 
                        color=department_colors.get(dept, "#DDDDDD"), alpha=0.5)
        
        # 处理同一时间点的步骤
        time_groups = {}
        for i, date in enumerate(step_dates):
            # 将时间点映射到新的范围内，保持时间比例
            days_from_start = (date - min_date).days
            scaled_position = timeline_start + (days_from_start / date_range) * timeline_width
            
            if scaled_position not in time_groups:
                time_groups[scaled_position] = []
            time_groups[scaled_position].append((step_names[i], date))
        
        # 绘制步骤
        sorted_positions = sorted(time_groups.keys())
        for idx, x_pos in enumerate(sorted_positions):
            steps_at_time = time_groups[x_pos]
            # 对于同一时间点的所有步骤，只画一个点
            ax.scatter(x_pos, y, color='black', zorder=3)
            
            # 获取这个时间点的所有步骤的日期
            current_date = steps_at_time[0][1]
            
            # 检查前后是否有相邻的日期点
            prev_date = None if idx == 0 else time_groups[sorted_positions[idx-1]][0][1]
            next_date = None if idx == len(sorted_positions)-1 else time_groups[sorted_positions[idx+1]][0][1]
            
            # 垂直排列同一时间点的步骤
            for i, (step, date) in enumerate(steps_at_time):
                # 计算文本框的水平位置
                text_x = x_pos
                
                # 如果与前一个点相差一天，向左偏移文本
                if prev_date and abs((date - prev_date).days) == 1:
                    if confirmation_period == 7:
                        text_x = x_pos + 0.0135
                    else:
                        text_x = x_pos + 0.0105
                # 如果与后一个点相差一天，向右偏移文本
                elif next_date and abs((date - next_date).days) == 1:
                    if confirmation_period == 7:
                        text_x = x_pos - 0.0135
                    else:
                        text_x = x_pos - 0.0105
                
                # 计算垂直偏移，对于同一天的步骤使用垂直堆叠
                if i == 0:
                    y_offset = -0.3  # 第一个步骤的偏移保持不变
                else:
                    # 如果是同一天的步骤，垂直堆叠
                    if date == current_date:
                        y_offset = -0.3 - i * 0.52
                    else:
                        # 如果是不同天的步骤，保持相同的垂直位置
                        y_offset = -0.3
                
                # 绘制文本框
                text_box = dict(boxstyle='round,pad=0.4', 
                              facecolor='white', 
                              alpha=1.0,  # Full opacity for sharper text
                              edgecolor='black', 
                              linewidth=1,
                              snap=True)  # Snap to pixel grid
                # 在点下方显示步骤名称和日期，调整字体大小
                step_text = f"{step}\n{date.strftime('%Y/%m/%d')}"
                
                # 特殊处理印布的印布后整，将其放在时间线上方
                if dept == "印布" and step == "印布后整":
                    y_offset = 0.3  # 将文本框放在时间线上方
                
                # 特殊处理面料的物理检测+验布，将文本框向右偏移
                if dept == "面料" and step == "物理检测+验布":
                    text_x += 0.01  # 向右偏移
                
                text = ax.text(text_x, y + y_offset, step_text, 
                               ha='center', 
                               va='bottom' if y_offset > 0 else 'top',
                               fontsize=16, 
                               color='black', 
                               fontweight='bold',
                               bbox=text_box,
                               zorder=5,  # Ensure text is above other elements
                               snap=True)  # Snap to pixel grid
        
        # 绘制实线连接
        x_positions = sorted(list(time_groups.keys()))
        if len(x_positions) > 1:
            ax.plot(x_positions, [y] * len(x_positions), '-', 
                   color='black', 
                   alpha=0.7, 
                   zorder=2,
                   linewidth=1.5,
                   solid_capstyle='round',
                   snap=True)  # Snap to pixel grid
    
    # 在右侧添加缝纫部分
    缝纫_steps = schedule["缝纫"]
    y_center = (max(y_positions.values()) + min(y_positions.values())) / 2
    ax.fill_betweenx([min(y_positions.values()) - 0.4, max(y_positions.values()) + 0.4], 
                     0.92, 1.0, color=department_colors["缝纫"], alpha=0.5)
    
    # 绘制缝纫步骤
    step_names = list(缝纫_steps.keys())
    step_dates = [缝纫_steps[step]["时间点"] for step in step_names]
    
    # 按时间顺序排序步骤
    sorted_steps = sorted(zip(step_names, step_dates), key=lambda x: x[1])
    
    # 计算x轴位置（在0.94-0.99之间平均分布）
    x_positions = []
    if len(sorted_steps) > 1:
        x_start = 0.93
        x_end = 0.99
        x_step = (x_end - x_start) / (len(sorted_steps) - 1)
        x_positions = [x_start + i * x_step for i in range(len(sorted_steps))]
    else:
        x_positions = [0.955]  # 如果只有一个步骤，放在中间
    
    # 绘制步骤和连接线
    for i, ((step, date), x_pos) in enumerate(zip(sorted_steps, x_positions)):
        # 绘制点
        ax.scatter(x_pos, y_center, color='black', zorder=3)
        
        # 为缝纫步骤添加文本框
        text_box = dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.8, edgecolor='black', linewidth=1)
        step_text = f"{step}\n{date.strftime('%Y/%m/%d')}"
        ax.text(x_pos, y_center - 0.3, step_text, ha='center', va='top',
               fontsize=16, color='black', fontweight='bold',
               bbox=text_box)
    
    # 绘制连接线
    if len(x_positions) > 1:
        ax.plot(x_positions, [y_center] * len(x_positions), '-', color='black', alpha=0.7, zorder=2)
    
    # 设置坐标轴
    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(y_positions.keys()), fontsize=22, fontweight='bold')  # 统一部门标签大小
    ax.set_xticks([])
    ax.set_xticklabels([])
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(min(y_positions.values()) - 0.7, max(y_positions.values()) + 0.7)  # 减小y轴的上下边距
    
    # 设置标题
    title_text = f"生产流程时间表 - {process_type}"
    if "style_number" in st.session_state and st.session_state["style_number"]:
        style_number_text = "款号: " + str(st.session_state["style_number"])
        # 将款号分成每行最多30个字符
        style_number_wrapped = [style_number_text[i:i+30] for i in range(0, len(style_number_text), 30)]
        title_text += "\n" + "\n".join(style_number_wrapped)
    ax.set_title(title_text, fontsize=30, fontweight='bold', y=1.02 + 0.02 * (len(style_number_wrapped) if 'style_number_wrapped' in locals() else 0))
    ax.set_frame_on(False)
    
    # 调整图形布局以适应文本框
    plt.subplots_adjust(left=0.1, right=0.9, bottom=0.1, top=0.98)
    
    return fig  # Return the figure instead of displaying it

# Function to generate department-specific plots
def generate_department_wise_plots(styles):
    all_schedules = []
    department_colors = {
        "面料": "#FFDDC1", 
        "印布": "#C1E1FF", 
        "裁剪1": "#D1FFC1", 
        "印花": "#FFC1E1", 
        "绣花": "#E1C1FF", 
        "裁剪2": "#FFD1C1", 
        "裁片库": "#C1FFD1", 
        "辅料": "#E1FFC1", 
        "缝纫": "#FFC1C1"
    }
    
    # Calculate schedules for all styles
    for style in styles:
        sewing_start_time = datetime.combine(style["sewing_start_date"], datetime.min.time())
        schedule = calculate_schedule(sewing_start_time, style["process_type"], style["cycle"])
        for dept, steps in schedule.items():
            for step, data in steps.items():
                all_schedules.append({
                    "style_number": style["style_number"],
                    "department": dept,
                    "step": step,
                    "date": data["时间点"],
                    "process_type": style["process_type"]
                })
    
    # Convert to DataFrame for sorting
    df = pd.DataFrame(all_schedules)
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Generate department-wise plots
    for department in df["department"].unique():
        dept_data = df[df["department"] == department].copy()
        
        # Sort by date (latest first) and then by style number
        dept_data.sort_values(by=["date", "style_number"], ascending=[False, True], inplace=True)
        
        # Calculate time range for dynamic sizing
        date_range = (dept_data["date"].max() - dept_data["date"].min()).days
        base_width = int(date_range/41*40)
        if base_width > 24:
            dpi_scale = base_width / 24
            plt.rcParams['figure.dpi'] = int(300 * dpi_scale)
            plt.rcParams['savefig.dpi'] = int(300 * dpi_scale)
        
        # Create figure with dynamic sizing
        fig, ax = plt.subplots(figsize=(max(base_width, 12), len(dept_data["style_number"].unique()) * 3))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        
        # Calculate y positions for each style number
        unique_styles = dept_data["style_number"].unique()
        y_positions = {style: idx * 1.5 for idx, style in enumerate(unique_styles)}
        
        # Create colored background for the department
        ax.fill_betweenx(
            [min(y_positions.values()) - 0.4, max(y_positions.values()) + 0.4],
            0, 1,
            color=department_colors.get(department, "#DDDDDD"),
            alpha=0.5
        )
        
        # Plot timeline for each style number
        for style in unique_styles:
            style_data = dept_data[dept_data["style_number"] == style]
            y = y_positions[style]
            
            # Convert dates to relative positions (0 to 1)
            date_min = dept_data["date"].min()
            date_max = dept_data["date"].max()
            total_days = (date_max - date_min).days
            
            # Sort steps by date
            style_data = style_data.sort_values(by="date")
            
            # Group steps by date
            date_groups = {}
            for _, row in style_data.iterrows():
                date_key = row["date"]
                if date_key not in date_groups:
                    date_groups[date_key] = []
                date_groups[date_key].append(row)
            
            # Plot points and labels for each date group
            x_positions = []
            dates = list(date_groups.keys())
            
            for date_idx, (date, rows) in enumerate(date_groups.items()):
                # Calculate x position
                if total_days == 0:
                    x_pos = 0.5  # Center of the timeline
                else:
                    days_from_start = (date - date_min).days
                    x_pos = 0.1 + (days_from_start / total_days) * 0.8  # Leave margins
                x_positions.append(x_pos)
                
                # Plot point
                ax.scatter(x_pos, y, color='black', zorder=3)
                
                # Calculate text position based on adjacent dates
                text_x = x_pos
                
                # Check if there's a previous or next date within 1 day
                prev_date = dates[date_idx-1] if date_idx > 0 else None
                next_date = dates[date_idx+1] if date_idx < len(dates)-1 else None
                
                scaling_factor = 0.02 + (0.08 * (1 - min(1, total_days / 20)))  # ✅ Adjust dynamically
                # Adjust text position if dates are 1 day apart
                if prev_date and abs((date - prev_date).days) == 1:
                    text_x = x_pos + scaling_factor#0.015  # Move right
                elif next_date and abs((date - next_date).days) == 1:
                    text_x = x_pos - scaling_factor#0.015  # Move left
                
                # Stack text boxes for steps on the same day
                for i, row in enumerate(rows):
                    text_box = dict(
                        boxstyle='round,pad=0.4',
                        facecolor='white',
                        alpha=1.0,
                        edgecolor='black',
                        linewidth=1
                    )
                    
                    # Calculate vertical offset for stacking
                    y_offset = -0.3 - i * 0.3  # Stack boxes vertically
                    
                    # Special handling for 印布后整, place it above the timeline
                    if department == "印布" and row["step"] == "印布后整":
                        y_offset = 0.3  # Place above the timeline
                    
                    step_text = f"{row['step']}\n{row['date'].strftime('%Y/%m/%d')}"
                    ax.text(
                        text_x, y + y_offset,
                        step_text,
                        ha='center',
                        va='bottom' if y_offset > 0 else 'top',  # Adjust vertical alignment based on position
                        fontsize=12,
                        fontweight='bold',
                        bbox=text_box,
                        zorder=5
                    )
            
            # Connect points with lines
            if len(x_positions) > 1:
                ax.plot(x_positions, [y] * len(x_positions), '-',
                       color='black',
                       alpha=0.7,
                       zorder=2,
                       linewidth=1.5)
        
        # Set up the axes
        ax.set_yticks(list(y_positions.values()))
        ax.set_yticklabels([f"款号: {style}" for style in y_positions.keys()],
                          fontsize=14,
                          fontweight='bold')
        ax.set_xticks([])
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(min(y_positions.values()) - 0.7, max(y_positions.values()) + 0.7)
        
        # Set title
        ax.set_title(department,
                    fontsize=24,
                    fontweight='bold',
                    y=1.02)
        ax.set_frame_on(False)
        
        # Save figure
        fig_path = os.path.join(temp_dir, f"{department}.png")
        fig.savefig(fig_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
    
    # Create ZIP archive
    zip_path = os.path.join(temp_dir, "Department_Timelines.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in os.listdir(temp_dir):
            if file.endswith(".png"):
                zipf.write(
                    os.path.join(temp_dir, file),
                    file  # Just use the filename directly
                )
    
    return zip_path

def adjust_schedule(schedule, department, delayed_step, new_end_time):
    if department not in schedule or delayed_step not in schedule[department]:
        return schedule
    
    delay_days = (new_end_time - schedule[department][delayed_step]["时间点"]).days
    found_delayed_step = False
    
    for step, times in schedule[department].items():
        if step == delayed_step:
            found_delayed_step = True
            schedule[department][step]["时间点"] = new_end_time
        elif found_delayed_step:
            schedule[department][step]["时间点"] += timedelta(days=delay_days)
    
    return schedule 

# Streamlit 界面
st.title("生产流程时间管理系统")

# 初始化 session state
if "all_styles" not in st.session_state:
    st.session_state["all_styles"] = []

# 创建输入表单
with st.form("style_input_form"):
    # 批量输入款号，每行一个
    style_numbers = st.text_area("请输入款号(每行一个):", "")
    sewing_start_date = st.date_input("请选择缝纫开始时间:", min_value=datetime.today().date())
    process_options = ["满花+局花+绣花", "满花+局花", "满花+绣花", "局花+绣花"]
    selected_process = st.selectbox("请选择工序:", process_options)
    cycle = st.selectbox("请选择确认周转周期:", [7, 14, 20])
    
    submitted = st.form_submit_button("添加款号")
    if submitted and style_numbers:
        # 分割多行输入，去除空行和空格
        new_style_numbers = [s.strip() for s in style_numbers.split('\n') if s.strip()]
        
        # 添加新的款号信息
        for style_number in new_style_numbers:
            new_style = {
                "style_number": style_number,
                "sewing_start_date": sewing_start_date,
                "process_type": selected_process,
                "cycle": cycle
            }
            st.session_state["all_styles"].append(new_style)
        st.success(f"已添加 {len(new_style_numbers)} 个款号")

# 显示当前添加的所有款号
if st.session_state["all_styles"]:
    st.subheader("已添加的款号:")
    
    # 使用列表来显示所有款号，并提供删除按钮
    for idx, style in enumerate(st.session_state["all_styles"]):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"{idx + 1}. 款号: {style['style_number']}, 工序: {style['process_type']}, 缝纫开始时间: {style['sewing_start_date']}, 周期: {style['cycle']}")
        with col2:
            if st.button("删除", key=f"delete_{idx}"):
                st.session_state["all_styles"].pop(idx)
                st.rerun()
    
    # 添加清空所有按钮
    if st.button("清空所有款号"):
        st.session_state["all_styles"] = []
        st.rerun()

# 生成图表按钮
if st.session_state["all_styles"]:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("生成所有生产流程图"):
            # 创建一个临时目录来存储图片
            with tempfile.TemporaryDirectory() as temp_dir:
                # 生成所有图表
                for style in st.session_state["all_styles"]:
                    sewing_start_time = datetime.combine(style["sewing_start_date"], datetime.min.time())
                    schedule = calculate_schedule(sewing_start_time, style["process_type"], style["cycle"])
                    
                    # 设置当前款号用于标题显示
                    st.session_state["style_number"] = style["style_number"]
                    fig = plot_timeline(schedule, style["process_type"], style["cycle"])
                    
                    # 保存图片 - 简化文件名
                    filename = f"{style['style_number']}_{style['process_type']}.png"
                    filepath = os.path.join(temp_dir, filename)
                    fig.savefig(filepath, dpi=300, bbox_inches='tight')
                    plt.close(fig)
                
                # 创建ZIP文件
                zip_path = os.path.join(temp_dir, "生产流程时间表.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in os.listdir(temp_dir):
                        if file.endswith('.png'):
                            zipf.write(os.path.join(temp_dir, file), file)
                
                # 提供ZIP文件下载
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="下载所有图片(ZIP)",
                        data=f,
                        file_name="生产流程时间表.zip",
                        mime="application/zip"
                    )
    
    with col2:
        if st.button("生成部门时间线图"):
            # 生成部门时间线图
            zip_path = generate_department_wise_plots(st.session_state["all_styles"])
            
            # 提供ZIP文件下载
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="下载部门时间线图(ZIP)",
                    data=f,
                    file_name="部门时间线图.zip",
                    mime="application/zip"
                )

# 调整生产流程部分保持不变
if "schedule" in st.session_state:
    st.subheader("调整生产流程")
    
    # 选择部门和步骤
    selected_dept = st.selectbox("选择部门:", list(st.session_state["schedule"].keys()))
    if selected_dept:
        delayed_step = st.selectbox("选择延误的工序:", list(st.session_state["schedule"][selected_dept].keys()))
        new_end_date = st.date_input("选择新的完成时间:", min_value=datetime.today().date())
        # 转换date为datetime
        new_end_time = datetime.combine(new_end_date, datetime.min.time())
        
        if st.button("调整生产时间"):
            st.session_state["schedule"] = adjust_schedule(
                st.session_state["schedule"],
                selected_dept,
                delayed_step,
                new_end_time
            )
            fig = plot_timeline(st.session_state["schedule"], selected_process, cycle)
            
            # Display the plot in Streamlit
            st.pyplot(fig)
            
            # Add download button for high-resolution image
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            st.download_button(
                label="下载高分辨率图片",
                data=buf,
                file_name=f"{style_number}_{selected_process}.png",
                mime="image/png"
            )
