"""Contract checks for visual iteration when Angular/PostgreSQL cannot run locally."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FRONT=ROOT/'frontend/src/app'


def test_home_is_root_but_catalogue_still_exists():
    routes=(FRONT/'app.routes.ts').read_text()
    assert "{path:'',pathMatch:'full',loadComponent:" in routes
    assert 'home.component' in routes
    assert "{path:'catalogo',loadComponent:" in routes
    assert "{path:'comparar',loadComponent:" in routes


def test_default_projection_is_real_orthographic():
    viewer=(ROOT/'frontend/src/bim/viewer.ts').read_text()
    assert "projection.set('Orthographic')" in viewer
    assert "await this.view('iso')" in viewer
    assert 'OrthoPerspectiveCamera' in viewer
    assert 'resize.observe(host)' in viewer


def test_two_column_shell_preserves_mounted_bim_on_navigation():
    shell=(FRONT/'features/solution-shell.component.ts').read_text()
    styles=(ROOT/'frontend/src/workbench.css').read_text()
    assert 'grid-template-columns:minmax(0,1fr) minmax(0,1fr)' in styles
    assert 'mobilePanel' in shell and 'show-mobile-data' in shell
    assert 'app-viewer-host' in shell
    assert "MAX_COMPARISON_ITEMS = 2" in (FRONT/'core/comparison-selection.ts').read_text() or 'MAX_COMPARISON_ITEMS=2' in (FRONT/'core/comparison-selection.ts').read_text()


def test_first_boot_depends_on_migration_and_blocks_frontend_until_healthy():
    compose=(ROOT/'compose.yaml').read_text()
    assert 'catalogue-init: {condition: service_completed_successfully}' in compose
    assert 'METRA_ADMIN_PASSWORD_FILE' in compose
    assert 'backend: {condition: service_healthy}' in compose


def test_all_delivery_documents_present():
    docs=ROOT/'docs'
    required=['ARCHITECTURE_FINAL.md','FINAL_CATALOGUE_INVENTORY.md',
              'DOCKER_FIRST_BOOT.md','DATA_MODEL.md',
              'POSTGRES_MIGRATION_AND_ROLLBACK.md','TEST_RESULTS_FINAL.md']
    assert all((docs/name).is_file() for name in required)
    assert not (docs/'archive').exists()
