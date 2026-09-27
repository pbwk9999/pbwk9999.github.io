# 我真的没病 · 越狱插件源

一套可以直接用的越狱源模板：Sileo / Zebra / Cydia 都能添加，索引由脚本自动生成，不需要装 dpkg。

- 源名：**我真的没病**
- 根地址：`https://pbwk9999.github.io/`
- 你要做的：把 deb 丢进 `debs/`，跑一次构建，推上去

## 一、根地址与公开部署

源地址：`https://pbwk9999.github.io/`

这是 GitHub Pages 的「用户站点」地址，对应 GitHub 账号 `pbwk9999` 和同名仓库 `pbwk9999.github.io`（公开、默认分支 `main`、Pages 的 Source 选 `GitHub Actions`）。末尾的 `/` 必须保留，客户端拼接 `Packages`、`Release`、deb 的相对路径时要靠它。

以后换地址时改这三处就够：

1. `repo.conf` 里的 `REPO_URL`（影响 `Release` 和索引）
2. `index.html` 里的 4 处（三个一键添加按钮加复制框）
3. `examples/hello-tweak/control` 里的 `Depiction` 和 `SileoDepiction`

改完跑一次构建，让 `Packages`、`Release`、插件一起更新。

> 这里发的插件只面向 Sileo / Zebra 安装：页面上不放 deb 直链，`debs/` 目录做了拦截，搜索引擎也屏蔽了，详见第九节。

用对象存储（OSS / COS / S3）或者自己的服务器也一样，只要支持 HTTPS 静态托管，把域名填进 `REPO_URL` 就行。

## 二、目录结构

```
pbwk9999-repo/
├── repo.conf            源配置，只改这里
├── build.sh             重建索引（macOS / Linux / CI）
├── build.ps1            重建索引（Windows）
├── Packages             索引，脚本生成
├── Packages.gz          压缩版索引，脚本生成
├── Packages.bz2
├── Release              源元数据，脚本生成
├── CydiaIcon.png        源图标，512x512
├── index.html           源的落地页（带一键添加按钮）
├── depictions.conf      每个包的详情页地址（可选，脚本自动读）
├── debs/                你的 deb 都放这里
├── depictions/          Cydia / Zebra 的详情页
├── sileodepiction/      Sileo 的原生详情页 JSON
├── examples/hello-tweak Theos 工程示例
├── tools/mkindex.py     索引生成器
├── tools/mkdeb.py       不开 Theos 也能打 deb
└── .github/workflows/   推代码自动重建并发布
```

## 三、日常只需要三步

1. 把插件 deb 放进 `debs/`
2. 重建索引
   - Windows：`powershell -ExecutionPolicy Bypass -File build.ps1`
   - macOS / Linux：`bash build.sh`
3. 推上去，客户端下拉刷新就能看到新版本

想给插件配详情页，就在 `depictions.conf` 里加一行（不配也能装，只是详情页空着）：

```
com.dcsyhi.zetsu.allinone = depictions/com.dcsyhi.zetsu.allinone/ | sileodepiction/com.dcsyhi.zetsu.allinone.json
```

索引脚本会扫描 `debs/` 下所有 `.deb`，把名字、版本、大小、MD5 / SHA1 / SHA256 写进 `Packages`，同时生成 `.gz`、`.bz2` 和 `Release`。忘了重建索引，用户就永远看不到更新，这是最常见的翻车点。

## 四、打包你的插件

### 用 Theos（推荐）

```
cd 你的插件目录
make package
```

产物在 `packages/` 里，复制到本仓库的 `debs/` 就行。

### 不用 Theos

`tools/mkdeb.py` 能把 control 加一个目录结构直接打成 deb：

```
python3 tools/mkdeb.py --control examples/hello-tweak/control --layout examples/hello-tweak/layout
```

`layout/` 里的目录结构就是设备上的真实结构。rootless 环境（Dopamine、palera1n rootless、roothide）放在 `layout/var/jb/` 下；老的 rootful 环境从 `layout/Library/` 开始。想在 Windows 上交叉打包带 dylib 的插件，记得权限位会丢，最好交给 GitHub Actions 打。

## 五、control 字段怎么写

```
Package: com.dcsyhi.zetsu.allinone
Name: 没病窗口工具
Version: 1.3.9
Architecture: iphoneos-arm64
Description: 这里是一句话简介
Maintainer: 你的名字 <你的邮箱>
Author: 你的名字 <你的邮箱>
Section: Tweaks
Depends: mobilesubstrate
Depiction: https://你的域名/depictions/com.dcsyhi.zetsu.allinone/
SileoDepiction: https://你的域名/sileodepiction/com.dcsyhi.zetsu.allinone.json
```

- `Architecture` 写错会直接导致客户端判定「不兼容此设备」而不显示：rootless / roothide 用 `iphoneos-arm64`，老 rootful 用 `iphoneos-arm`
- `Icon` 想显示插件图标就写 `file:///var/jb/Library/PreferenceBundles/xxx.bundle/icon.png`（rootless 路径前缀是 `/var/jb`）
- 每次发新版都要把 `Version` 往上加，否则客户端认为是同一个包

## 六、部署到 GitHub Pages（免费）

1. 新建仓库，把整个目录推上去，默认分支用 `main`（工作流就是这么配的）
2. 仓库 Settings → Pages → Source 选 `GitHub Actions`
3. 之后每次 push，`.github/workflows/repo.yml` 会自动重建索引并发布
4. GitHub Pages 会给你一个 `https://<用户名>.github.io/<仓库名>/` 的地址；想用它的话，把 `repo.conf` 的 `REPO_URL`、`index.html` 里的 4 处、`control` 里的 2 行一起换掉再推

私有仓库的 Pages 需要付费账号；单个文件不要超过 100 MB，deb 太大就改用对象存储（OSS / COS / S3）。

## 七、让 Sileo 显示好看的详情页

- Cydia / Zebra 看 `Depiction` 指向的 `depictions/<包名>/index.html`
- Sileo 看 `SileoDepiction` 指向的 `sileodepiction/<包名>.json`

两套样板就是 `depictions/` 和 `sileodepiction/` 里的那份，复制改包名即可；配好之后写进 `depictions.conf`，重建索引时会自动写进 `Packages`。详情页一定要带 viewport meta，不然在手机上排版会炸。

## 八、上线前先本地自测

在仓库根目录执行：

```
python3 -m http.server 8000
```

然后在 Sileo 里添加 `http://你电脑的局域网IP:8000/`，能正常看到并安装你的插件，就说明索引、路径、安装包这一整条链路都是通的。正式上线请用 HTTPS，Sileo 对纯 HTTP 源会报警告。

## 九、只给客户端装，不给单独下载

`debs/` 里放了一个 `index.html`：别人直接点开 `debs/` 只会看到「这里不提供单独下载，请用 Sileo 安装」的提示页；`robots.txt` 把 `debs/` 屏蔽掉，搜索引擎不会收录插件文件；插件详情页里也不放 deb 的下载链接，用户就只能走 Sileo / Zebra 点安装。

要说清楚的是：客户端下载 deb 时走的就是那个直链，所以文件本身没法真正锁死，能挡住的是「页面上有下载入口」。要彻底禁止直链，得自己搭服务器做签名校验。

## 十、常见问题

- **加了源但看不到包**：九成是 `Architecture` 和设备不匹配。
- **看不到新版本**：忘了重建索引，或者改动没推上去。
- **安装时报 404**：`Packages` 里的 `Filename` 必须和 `debs/` 里真实文件名一致，改过文件名就重跑构建。
- **源图标没变**：Sileo 会缓存，删掉源重新加一次。
- **GitHub Pages 打开 404**：确认 Pages 的 Source 是 `GitHub Actions`，并且工作流成功跑完了。
- **想加 GPG 签名**：客户端不强制校验，需要的话用 `apt-ftparchive` 和 `gpg` 给 `Release` 签名，其余不用改。
