# 示例：提审前用脚本扫一遍项目

> 迷你项目是为演示构造的（故意埋了常见问题），输出是脚本对它的真实运行结果，节选部分没有改动文字。扫描结果是风险信号，不是审核结论。

## 用户原话（示例）

> 第一次提审，想一次过。项目在 mini-demo 目录，隐私保护指引里目前声明了位置、相册和手机号。

## 输入

项目结构（节选）：

```
mini-demo/
├── project.config.json          miniprogramRoot 为 miniprogram/，urlCheck 为 false
├── declared.txt                 getLocation / chooseMedia / 手机号
└── miniprogram/
    ├── app.json                 pages 里 index 重复；tabBar 指向不存在的 pages/mine/mine；requiredPrivateInfos 只有 chooseLocation
    ├── app.js                   onLaunch 里调用 wx.getLocation
    ├── pages/index/             请求 http://203.0.113.5/api/list；navigateTo 到未注册的 /pages/detail/detail；
    │                            文案「新人专享：分享到3个群即可解锁全部功能」「更多功能敬请期待」
    ├── pages/profile/           只有 profile.js，缺 profile.wxml
    ├── pages/share/             chooseMedia、setClipboardData、requestPayment；「邀请3位好友助力，免费领取会员」
    ├── pages/old/               没注册的旧页面
    ├── packageA/pages/detail/   请求 https://api.example.com；调用 wx.chooseAddress
    └── components/card/         自定义组件（不应被当成废弃页面）
```

## 命令

```bash
python3 scripts/mp_precheck.py mini-demo --declared mini-demo/declared.txt
```

## 输出（节选，退出码 0）

```
【风险清单】（高 → 中 → 提示；是风险信号，不是审核结论）
[高] NAV-TARGET 跳转目标页面未注册：pages/detail/detail
      位置：pages/index/index.js:7  wx.navigateTo({ url: '/pages/detail/deta…
      建议：改成已注册的页面路径（分包页面要带分包 root）
[高] NAV-TARGET navigator 跳转目标未注册：pages/help/help
      位置：pages/index/index.wxml:4  <navigator url="/pages/help/help">帮助中心</…
      建议：改成已注册的页面路径
[高] PAGE-MISSING 已注册的页面缺文件，审核打开会报错或白屏
      位置：pages/profile/profile 缺 .wxml
      建议：补齐文件或从 app.json 删除该页面
[高] TABBAR tabBar 指向的页面不在主包 pages 里
      位置：pages/mine/mine
      建议：把该页面加入主包 pages，或修改 tabBar 配置
[高] LOC-RPI-chooseAddress 接口 chooseAddress 没写进 app.json 的 requiredPrivateInfos
      位置：packageA/pages/detail/detail.js:4
      建议：在 app.json 的 requiredPrivateInfos 里加上 chooseAddress（常见要求，以官方文档为准）
[高] LOC-RPI-getLocation 接口 getLocation 没写进 app.json 的 requiredPrivateInfos
      位置：app.js:4
      建议：在 app.json 的 requiredPrivateInfos 里加上 getLocation（常见要求，以官方文档为准）
[高] PRIV-chooseAddress 用到 wx.chooseAddress（通讯地址），但声明清单里没有
      位置：packageA/pages/detail/detail.js:4
      建议：在《用户隐私保护指引》里补充声明，或删除这处调用
[高] PRIV-getUserProfile 用到 wx.getUserProfile（用户信息），但声明清单里没有
      位置：pages/index/index.js:4
      建议：在《用户隐私保护指引》里补充声明，或删除这处调用
[高] PRIV-setClipboardData 用到 wx.setClipboardData（剪切板），但声明清单里没有
      位置：pages/share/share.js:3
      建议：在《用户隐私保护指引》里补充声明，或删除这处调用
[高] NET-IP 请求地址用的是 IP
      位置：pages/index/index.js:3  http://203.0.113.5/api/list
      建议：换成已备案并配置到后台的 HTTPS 域名（常见要求）
[高] INDUCE 疑似诱导分享、关注或拉好友的文案
      位置：pages/index/index.wxml:1  新人专享：分享到3个群即可解锁全部功能
      建议：去掉以分享、关注、拉好友换取功能或奖励的设计；分享只作为可选操作
[高] INDUCE 疑似诱导分享、关注或拉好友的文案
      位置：pages/share/share.wxml:1  邀请3位好友助力，免费领取会员
      建议：去掉以分享、关注、拉好友换取功能或奖励的设计；分享只作为可选操作
[中] NAV-SWITCHTAB switchTab 只能跳 tabBar 页面：pages/share/share
[中] PAGE-DUP 页面重复注册
[中] AUTH-TIMING 小程序启动时（app.js）就调用了 getLocation
[中] LOC-DESC-getLocation 调用 getLocation 但 app.json 的 permission 里没有 scope.userLocation 的用途说明
[中] USERINFO-getUserProfile 调用了 wx.getUserProfile：官方调整过头像昵称的获取方式，可能拿不到真实信息
[中] TESTCONTENT 疑似测试或未完成内容
      位置：pages/index/index.wxml:3  更多功能敬请期待
[中] TESTCONTENT 疑似测试或未完成内容
      位置：pages/share/share.json:1  测试数据页
[提示] AUTH-FIRSTPAGE 首页脚本里有授权相关调用
[提示] CFG-URLCHECK 开发者工具关闭了合法域名校验（urlCheck: false）
[提示] NET-DOMAINS 代码里用到的 HTTPS 域名
[提示] PAY-VIRTUAL 有支付调用，且文案涉及会员、课程、充值等虚拟商品或服务
[提示] UGC 用户可以发布内容（有输入框、上传或提交，且有发布、评论类文案）
[提示] ORPHAN 有页面文件但没在 app.json 注册（可能是废弃页面）

汇总：高 12 / 中 7 / 提示 6。规则以《微信小程序运营规范》及官方平台通知的最新版本为准。
```

（节选：开头的【输入】与结尾的人工核对清单省略；「中」「提示」两组为节省篇幅省略了部分「位置」「建议」行，其余逐字保留。WXML 注释里的旧文案「集赞送礼」没有被扫到，自定义组件 components/card 没有被当成废弃页面。）

## 助手的交付物（按输出契约）

```
【结论】当前版本不建议提审：12 项「高」里有 4 项会直接导致页面打不开或跳转失败。
【必须先改（高）】
1. 页面与跳转：补 profile.wxml；tabBar 去掉 pages/mine/mine 或补上该页；
   /pages/detail/detail 改为 /packageA/pages/detail/detail；删除或补上 /pages/help/help
2. 网络：203.0.113.5 换成已配置的 HTTPS 域名
3. 隐私：chooseAddress、getUserProfile、setClipboardData 要么补声明，要么删调用；
   requiredPrivateInfos 补 getLocation、chooseAddress
4. 诱导：删除「分享到3个群即可解锁」「邀请3位好友助力，免费领取会员」，功能与会员不再和分享挂钩
【建议改（中）】位置授权从 app.js 挪到用户点「附近门店」时；permission 写 scope.userLocation 用途；
  头像昵称改用官方填写能力；删掉「敬请期待」入口，页面标题「测试数据页」改正式名称
【人工核对（脚本看不到）】类目是否覆盖「会员 + 支付」；虚拟商品支付的 iOS 端限制以官方最新说明为准；
  评论功能要有内容审核与举报入口；提审说明写清体验路径
【复扫】改完重跑，「高」清零后再提审
```
