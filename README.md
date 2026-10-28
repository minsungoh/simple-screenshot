# 스크린샷 메모

Ubuntu 24.04 기본 캡처 도구 뒤에 붙는 개인용 편집기입니다.
빨간 펜 하나만 제공합니다.

## 실행

```bash
cd /home/msoh/workspace/simple-scritshot
/usr/bin/python3 screenshot_note.py
```

실행해 둔 상태에서 `Print Screen` → 마우스로 영역 선택 → 캡처하면 편집 창이 열립니다.
드래그해서 빨간 선을 그리고 `Ctrl+C` 또는 **복사 후 닫기**를 누릅니다.
`Esc`는 마지막 선 하나를 취소합니다. 창의 닫기 버튼은 복사 없이 닫습니다.
복사한 이미지는 다른 앱에 `Ctrl+V`로 붙여 넣습니다.

기본 캡처가 `사진/Screenshots` 폴더에 새로 저장하는 파일을 감지합니다.
기존 파일은 열지 않으며 기본 캡처의 원본 파일도 수정하지 않습니다.
일반 이미지 복사에는 반응하지 않습니다.
큰 이미지는 화면에서만 축소하며 복사본은 원본 크기를 유지합니다.
편집 창을 닫아도 다음 캡처 감지와 클립보드 유지를 위해 프로그램은 상주합니다.

```bash
# 상주 프로그램 종료
/usr/bin/python3 screenshot_note.py --quit

# 캡처 없이 특정 이미지 편집
/usr/bin/python3 screenshot_note.py --image /절대/경로/이미지.png

# 별도 저장 폴더를 쓰는 경우 (기존 프로그램 종료 후 실행)
/usr/bin/python3 screenshot_note.py --watch-dir /절대/경로/스크린샷폴더
```

필요한 시스템 패키지는 `python3-gi`, `gir1.2-gtk-3.0`, `python3-pil`입니다.
현재 작업 PC에서는 모두 설치되어 있습니다.
현재 PC에는 `~/.config/autostart/screenshot-note.desktop`으로 시작 프로그램을 등록했습니다.
Ubuntu 로그인 시 자동으로 실행되므로 재부팅 후 직접 실행할 필요가 없습니다.
자동 실행을 끄려면 Ubuntu의 **시작 프로그램**에서 **스크린샷 메모**를 비활성화합니다.

GNOME(우분투 기본 데스크톱)의 창 활성화 정책에 따라 편집 창 대신 알림이 나타날 수 있습니다.
이 경우 알림이나 작업 표시줄에서 편집 창을 선택합니다.
기본 캡처의 파일 저장을 끈 환경에서는 자동 감지가 동작하지 않습니다.

기본 캡처 동작: https://help.gnome.org/gnome-help/screen-shot-record.html
