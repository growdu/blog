# 使用mdbook编译html和pdf

```shell
cargo install mdbook
dnf install -y chromium
chromium-browser --version
dnf install -y   google-noto-serif-cjk-fonts   google-noto-sans-cjk-fonts
cargo install mdbook-pdf
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox-0.12.6.1-3.almalinux8.x86_64.rpm
dnf install -y wkhtmltox-0.12.6.1-3.almalinux8.x86_64.rpm
wkhtmltopdf --help
```

往book.toml里添加如下内容：

```toml
[output.pdf]
command = "mdbook-pdf"

[output.pdf.render]
toc = true
```

然后执行：

```shell
mdbook build
```