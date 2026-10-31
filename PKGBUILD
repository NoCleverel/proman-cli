# Maintainer: Clever Elvin <cleverel@student.21-school.ru>
pkgname=proman-cli
pkgver=0.3.0
pkgrel=1
pkgdesc="Standardized Git workflow, project launcher, and SSH key manager"
arch=('any')
url="https://github.com/cleverelhome-cloud/proman-cli"
license=('MIT')
depends=('python' 'python-typer' 'python-rich')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('be2894b43f78c0fda880987b4b4bce52c68936123619a1cbddc9a5a59f56fab0')

build() {
  cd "$pkgname-$pkgver"
  python -m build --wheel --no-isolation
}

package() {
  cd "$pkgname-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl
  install -Dm644 docs/proman.1 "$pkgdir/usr/share/man/man1/proman.1"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
