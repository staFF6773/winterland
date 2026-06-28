# Maintainer: Frostwall Team <dev@example.com>
pkgname=frostwall
pkgver=1.0.0
pkgrel=1
pkgdesc="Minimalist wallpaper manager for Hyprland with dynamic Wallust theming"
arch=('any')
url="https://github.com/example/frostwall"
license=('MIT')
depends=(
    'python>=3.12'
    'python-pyside6'
    'python-pillow'
    'python-watchdog'
    'python-psutil'
    'python-toml'
    'hyprpaper'
    'mpvpaper'
    'hyprland'
    'mpv'
)
makedepends=(
    'python-setuptools'
    'python-build'
    'python-installer'
    'python-wheel'
)
optdepends=(
    'wallust: automatic color theming from wallpaper'
)
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.whl

    install -Dm644 "assets/icons/app.svg" \
        "${pkgdir}/usr/share/icons/hicolor/scalable/apps/frostwall.svg"

    install -Dm644 "${srcdir}/${pkgname}-${pkgver}/assets/frostwall.desktop" \
        "${pkgdir}/usr/share/applications/frostwall.desktop"

    install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
