import logging
import requests
from bs4 import BeautifulSoup
from src.config import (
    BASE_URL,
    URL_JORNADA,
    URL_CLASIFICACION,
    DEFAULT_PARAMS,
    USER_AGENT,
    HTTP_TIMEOUT,
)

logger = logging.getLogger(__name__)


class AsturfutbolClient:
    """Cliente HTTP para interactuar con asturfutbol.es gestionando cookies de sesión."""

    def __init__(self, timeout: int = HTTP_TIMEOUT):
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        })
        self._session_initialized = False

    def _ensure_session(self):
        """Inicializa la sesión visitando la portada para aceptar cookies (JSESSIONID)."""
        if not self._session_initialized:
            logger.debug("Inicializando sesión en portada de asturfutbol...")
            resp = self.session.get(BASE_URL, timeout=self.timeout)
            resp.raise_for_status()
            self._session_initialized = True

    def get_html(self, url: str, params: dict = None) -> str:
        """Realiza una petición GET devolviendo el HTML decodificado en ISO-8859-15."""
        self._ensure_session()
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        resp.encoding = "iso-8859-15"
        
        # Verificar que no devuelva la página de bloqueo de cookies
        if "No se ha aceptado el cookie" in resp.text:
            logger.warning("Cookie no aceptada detectada, reinicializando sesión...")
            self._session_initialized = False
            self._ensure_session()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = "iso-8859-15"
            
        return resp.text

    def get_soup(self, url: str, params: dict = None) -> BeautifulSoup:
        html = self.get_html(url, params)
        return BeautifulSoup(html, "html.parser")

    def get_jornada_soup(self, cod_jornada: int = None) -> BeautifulSoup:
        params = dict(DEFAULT_PARAMS)
        if cod_jornada is not None:
            params["CodJornada"] = cod_jornada
        return self.get_soup(URL_JORNADA, params=params)

    def get_clasificacion_soup(self, cod_jornada: int = None) -> BeautifulSoup:
        params = dict(DEFAULT_PARAMS)
        if cod_jornada is not None:
            params["codjornada"] = cod_jornada
        return self.get_soup(URL_CLASIFICACION, params=params)
