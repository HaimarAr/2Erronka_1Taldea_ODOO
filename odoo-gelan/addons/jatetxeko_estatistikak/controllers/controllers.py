# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import requests
from dateutil import parser
from datetime import datetime

class MyController(http.Controller):
    @http.route('/gorde_datuak_langileak', auth='public', methods=['GET'], csrf=False)
    def obtener_datos_api(self, **kwargs):
        email = kwargs.get('email')
        try:
            api_url = "http://host.docker.internal:80/langileak_konexioa.php"
            params = {'email': email} if email else {}
            response = requests.get(api_url, params=params)
            
            if response.status_code != 200:
                return json.dumps({"status_code": 500, "mezua": "Error en la API externa"})
        
            langileak_data = response.json()
            created_count = 0
            updated_count = 0
        
            if 'langileak' in langileak_data and langileak_data.get('status_code') == 200:
                Zerbitzaria = request.env['jatetxeko_estatistikak.zerbitzaria'].sudo()
                
                for langilea in langileak_data['langileak']:
                    if email and langilea.get('email') != email:
                        continue
                    
                    existing_record = Zerbitzaria.search([('email', '=', langilea.get('email'))], limit=1)
                    
                    vals = {
                        'name': langilea.get('name'),
                        'abizena': langilea.get('abizena'),
                        'email': langilea.get('email'),
                    }
                    
                    if existing_record:
                        existing_record.write(vals)
                        updated_count += 1
                    else:
                        Zerbitzaria.create(vals)
                        created_count += 1
        
                return json.dumps({
                    "status_code": 200,
                    "mezua": f"Sincronizado: {created_count} creado(s), {updated_count} actualizado(s)"
                })
            else:
                return json.dumps({"status_code": 500, "mezua": "No hay datos válidos"})
        
        except Exception as e:
            return json.dumps({"status_code": 500, "mezua": str(e)})

    @http.route('/gorde_datuak_eskaerak', auth='public', methods=['GET'], csrf=False)
    def obtener_eskaerak_api(self, **kwargs):
        id = kwargs.get('id')
        try:
            api_url = "http://host.docker.internal:80/eskaera_konexioa.php"
            params = {'id': id} if id else {}
            response = requests.get(api_url, params=params)
            
            if response.status_code != 200:
                return json.dumps({
                    "status_code": 500,
                    "mezua": "Errorea kanpoko API-an"
                })
        
            eskaerak_data = response.json()
            created_count = 0
            updated_count = 0
        
            if eskaerak_data.get('status_code') == 200 and ('eskaerak' in eskaerak_data or 'eskaera' in eskaerak_data):
                Eskaera = request.env['jatetxeko_estatistikak.eskaera'].sudo()
                
                data_to_process = []
                if 'eskaerak' in eskaerak_data:
                    data_to_process = eskaerak_data['eskaerak']
                elif 'eskaera' in eskaerak_data:
                    data_to_process = [eskaerak_data['eskaera']]
                
                for eskaera in data_to_process:
                    existing_record = Eskaera.search([('id', '=', eskaera.get('id'))], limit=1)
                    
                    langilea = False
                    if eskaera.get('langilea_email'):
                        langilea = request.env['jatetxeko_estatistikak.zerbitzaria'].sudo().search(
                            [('email', '=', eskaera.get('langilea_email'))], limit=1)
                    
                    mahaia = False
                    if eskaera.get('mahaia_zenbakia'):
                        mahaia = request.env['jatetxeko_estatistikak.mahaia'].sudo().search(
                            [('zenbakia', '=', eskaera.get('mahaia_zenbakia'))], limit=1)
                    
                    vals = {
                        'langilea_id': langilea.id if langilea else False,
                        'mahaia_id': mahaia.id if mahaia else False,
                        'egoera': str(eskaera.get('egoera', '0')),
                        'done': bool(eskaera.get('done', False)),
                        'EskaeraDone': bool(eskaera.get('EskaeraDone', False)),
                        'ordainduta': bool(eskaera.get('ordainduta', False)),
                    }
                    
                    if existing_record:
                        existing_record.write(vals)
                        updated_count += 1
                    else:
                        Eskaera.create(vals)
                        created_count += 1
        
                return json.dumps({
                    "status_code": 200,
                    "mezua": f"Sinkronizatua: {created_count} sortu, {updated_count} eguneratu"
                })
            else:
                return json.dumps({
                    "status_code": 404,
                    "mezua": "Ez daude daturik edo errorea"
                })
        
        except Exception as e:
            return json.dumps({
                "status_code": 500,
                "mezua": f"Errorea: {str(e)}"
            })

class MahaiaSyncController(http.Controller):
    @http.route('/gorde_datuak_mahaia', auth='public', methods=['GET'], csrf=False)
    def obtener_mahaia_api(self, **kwargs):
        zenbakia = kwargs.get('zenbakia')  
        try:
            api_url = "http://host.docker.internal:80/mahaia_konexioa.php" 
            params = {'zenbakia': zenbakia} if zenbakia else {}
            response = requests.get(api_url, params=params)
            
            if response.status_code != 200:
                return json.dumps({
                    "status_code": 500,
                    "mezua": "Errorea kanpoko API-an"
                })
        
            mahaia_data = response.json()
            created_count = 0
            updated_count = 0
        
            if mahaia_data.get('status_code') == 200 and 'mahaia' in mahaia_data:
                Mahaia = request.env['jatetxeko_estatistikak.mahaia'].sudo()
                
                data_to_process = mahaia_data['mahaia'] if isinstance(mahaia_data['mahaia'], list) else [mahaia_data['mahaia']]
                
                for mahaia in data_to_process:
                    existing_record = Mahaia.search([('zenbakia', '=', mahaia.get('zenbakia'))], limit=1)
                    
                    updated_at = mahaia.get('updated_at')
                    if updated_at:
                        try:
                            parsed_date = parser.isoparse(updated_at)
                            updated_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    vals = {
                        'zenbakia': mahaia.get('zenbakia'),
                        'eserlekuak': mahaia.get('eserlekuak'),
                        'habilitado': bool(mahaia.get('habilitado')),
                        'terraza': mahaia.get('terraza'),
                        'updated_at': updated_at,
                    }
                    
                    if existing_record:
                        existing_record.write(vals)
                        updated_count += 1
                    else:
                        Mahaia.create(vals)
                        created_count += 1
        
                return json.dumps({
                    "status_code": 200,
                    "mezua": f"Sinkronizatua: {created_count} sortu, {updated_count} eguneratu"
                })
            else:
                return json.dumps({
                    "status_code": 404,
                    "mezua": "Ez daude daturik edo errorea"
                })
        
        except Exception as e:
            return json.dumps({
                "status_code": 500,
                "mezua": f"Errorea: {str(e)}"
            })

class PlateraSyncController(http.Controller):

    @http.route('/gorde_datuak_platera', auth='public', methods=['GET'], csrf=False)
    def obtener_platera_api(self, **kwargs):
        platera_id = kwargs.get('id')  # Obtenemos el id de los parámetros de la URL
        try:
            api_url = "http://host.docker.internal:80/platera_konexioa.php"
            params = {'id': platera_id} if platera_id else {}
            response = requests.get(api_url, params=params)

            if response.status_code != 200:
                return json.dumps({
                    "status_code": 500,
                    "mezua": "Errorea kanpoko API-an"
                })

            platera_data = response.json()
            created_count = 0
            updated_count = 0

            if platera_data.get('status_code') == 200:
                Platera = request.env['jatetxeko_estatistikak.platera'].sudo()

                data_to_process = platera_data['platerak'] if 'platerak' in platera_data else [platera_data['platera']] if 'platera' in platera_data else []

                for platera in data_to_process:
                    existing_record = Platera.search([('external_id', '=', str(platera.get('id')))], limit=1)

                    created_at = platera.get('created_at')
                    if created_at:
                        try:
                            parsed_date = parser.isoparse(created_at)
                            created_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                parsed_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                                created_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    updated_at = platera.get('updated_at')
                    if updated_at:
                        try:
                            parsed_date = parser.isoparse(updated_at)
                            updated_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            # Intentamos el formato de la API (29/01/2025 13:11:51)
                            try:
                                parsed_date = datetime.strptime(updated_at, '%d/%m/%Y %H:%M:%S')
                                updated_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    deleted_at = platera.get('deleted_at')
                    if deleted_at:
                        try:
                            parsed_date = parser.isoparse(deleted_at)
                            deleted_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                parsed_date = datetime.strptime(deleted_at, '%Y-%m-%d %H:%M:%S')
                                deleted_at = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                deleted_at = False
                    else:
                        deleted_at = False

                    vals = {
                        'external_id': str(platera.get('id')),
                        'izena': platera.get('izena', ''),
                        'deskribapena': platera.get('deskribapena', ''),
                        'mota': platera.get('mota', ''),
                        'platera_mota': platera.get('platera_mota', ''),
                        'prezioa': float(platera.get('prezioa', 0.0)),
                        'menu': bool(int(platera.get('menu', 0))),
                        'created_at': created_at,
                        'created_by': str(platera.get('created_by', '')),
                        'updated_at': updated_at,
                        'updated_by': str(platera.get('updated_by', '')),
                        'deleted_at': deleted_at,
                        'deleted_by': str(platera.get('deleted_by', '')),
                    }

                    if existing_record:
                        existing_record.write(vals)
                        updated_count += 1
                    else:
                        Platera.create(vals)
                        created_count += 1

                return json.dumps({
                    "status_code": 200,
                    "mezua": f"Sinkronizatua: {created_count} sortu, {updated_count} eguneratu"
                })
            else:
                return json.dumps({
                    "status_code": 404,
                    "mezua": "Ez daude daturik edo errorea"
                })

        except Exception as e:
            return json.dumps({
                "status_code": 500,
                "mezua": f"Errorea: {str(e)}"
            })