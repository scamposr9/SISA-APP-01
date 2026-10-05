from acta_app.encuesta_correo import errores_correo, sugerencia_correo


def test_correo_del_cliente_es_opcional_pero_debe_coincidir_y_ser_valido():
    assert errores_correo("", "") == []
    assert errores_correo("Ana@Hospital.pe", " ana@hospital.pe") == []
    assert "no coinciden" in errores_correo("ana@hospital.pe", "ana@hospital.com")[0]
    assert "formato" in errores_correo("ana-hospital.pe", "ana-hospital.pe")[0]
    assert "Sistemas Analíticos" in errores_correo("yo@sistemasanaliticos.com", "yo@sistemasanaliticos.com")[0]


def test_sugiere_dominios_mal_escritos():
    assert sugerencia_correo("ana@gmial.com") == "ana@gmail.com"
    assert sugerencia_correo("ana@hospital.pe") is None
