# seuLectRsv
A script for SEU automatic lecture reservation.

Tips:
 - This script requires `requests`, `pycryptodome` and `ddddocr` to work properly. Use `pip install -r requirements.txt` for a quick start.
 - Edit **config.json** before running the script.
     - `onlineOnly` determines whether the script will ignore all offline lectures.
     - `district` filters the lecture list with certain campus area. The available choices are `四牌楼校区`, `九龙湖校区`, `丁家桥校区`, `苏州校区` and `无锡分校`.
     - `filter` is used to focus on certain lecture categories. The list's order determines the choosing priority. The available choices are `心理`, `法律`, `艺术`, `其他` and `非讲座`.
 - Check configExample.json for tutorial.

Update 2024-11-10:
* Enhanced logic:
  * No longer triggers rate limiting when matched lecture is cancelled.
    * Great thanks to [xzza1931](https://github.com/xzza1931) for finding a workaround.
  * Add support for multiple campus district choice.
* Display filtered lecture list for convenience.
* **Still not fully tested. Any volunteers?**

Update 2024-10-19:
* Switching to seulectrsvnext.py, tackling with newly emerged certificate issues.
* This is still a prototype, need more testing.

Edit: This project is no longer facing env-related issues due to updated ddddocr project.

~~This project is currently (2023-11-6) experiencing environment-setting problems, caused by the conflicts between the latest version of ddddocr and pillow. Feel free to open an Issue or make a Pull request.~~