import shutil
import os

dev_ico = "assets/queqq_dev.ico"
dev_png = "assets/queqq_dev.png"

app_ico = "assets/app.ico"
icon_png = "assets/icon.png"

if os.path.exists(dev_ico):
    shutil.copyfile(dev_ico, app_ico)
    print(f"Copied {dev_ico} -> {app_ico}")

if os.path.exists(dev_png):
    shutil.copyfile(dev_png, icon_png)
    print(f"Copied {dev_png} -> {icon_png}")
