import PyInstaller.__main__
import os

# 打包程序
def package_exe(code_path, icon_path=None, save_dir='', is_onefile=True, is_windowed=True):
    """
    用PyInstaller打包Python脚本为exe的核心函数

    参数说明：
    script_path  : 必需，待打包的Python脚本绝对路径（如"D:/test/script.py"）
    icon_path    : 可选，图标文件绝对路径（必须是.ico格式，默认无图标）
    is_onefile   : 可选，是否打包为单文件（True=--onefile，False=--onedir，默认True）
    is_windowed  : 可选，是否窗口模式（True=无控制台，False=有控制台，默认False）
    save_dir     : 可选，打包结果保存目录（默认当前目录）
    """

    script_path = code_path
    if not script_path:
        return
    icon_path = icon_path
    is_onefile = is_onefile
    is_windowed = is_windowed
    save_dir = save_dir

    # 1. 验证核心参数
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"待打包脚本不存在：{script_path}")

    if icon_path:  # 若指定了图标
        if os.path.splitext(icon_path)[1].lower() != ".ico":
            raise ValueError("图标文件必须是.ico格式")
        if not os.path.exists(icon_path):
            raise FileNotFoundError(f"图标文件不存在：{icon_path}")

    if not os.path.exists(save_dir):
        raise FileNotFoundError(f"保存目录不存在：{save_dir}")

    pack_args = [
        script_path,  # 必选：待打包脚本路径
        f'--distpath={save_dir}',  # 指定打包结果保存目录
        f"--specpath=spec",  # 指定 spec 文件路径
    ]

    # 添加图标参数（若有）
    if icon_path:
        pack_args.extend(["-i", icon_path])

    pack_args.append("--onefile" if is_onefile else "--onedir")

    if is_windowed:
        pack_args.append("--windowed")  # 无控制台

    # 3. 执行打包
    print(f"开始打包，参数：{pack_args}")
    PyInstaller.__main__.run(pack_args)
    print(f"打包完成，结果保存至：{save_dir}")

