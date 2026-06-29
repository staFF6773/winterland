# Maintainer: staFF6773
pkgname=winterland
pkgver=1.0.0
pkgrel=1
pkgdesc="Static and Animated Wallpaper Manager for Hyprland"
arch=('any')
url="https://github.com/staFF6773/winterland"
license=('GPL-3.0-or-later')
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
    'imagemagick'
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

    # Scalable SVG icon
    install -Dm644 "assets/icons/app.svg" \
        "${pkgdir}/usr/share/icons/hicolor/scalable/apps/winterland.svg"

    # Generate PNG icons at standard hicolor sizes
    for _size in 16 24 32 48 64 128 256 512; do
        install -Dm644 <(convert "assets/winterland.png" \
            -resize "${_size}x${_size}" png:-) \
            "${pkgdir}/usr/share/icons/hicolor/${_size}x${_size}/apps/winterland.png"
    done

    # Desktop entry
    install -Dm644 "assets/winterland.desktop" \
        "${pkgdir}/usr/share/applications/winterland.desktop"

    # License
    install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
