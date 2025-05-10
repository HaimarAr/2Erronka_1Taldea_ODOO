# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import requests
import logging
from odoo.exceptions import UserError, ValidationError
from dateutil import parser
from datetime import datetime  # Asegúrate de que esta línea esté presente

_logger = logging.getLogger(__name__)

class Zerbitzaria(models.Model):
    _name = 'jatetxeko_estatistikak.zerbitzaria'
    _description = 'Zerbitzaria'
    _rec_name = 'worker_id'  # Añadido para asegurar que Odoo tenga un campo por defecto

    worker_id = fields.Char(string="Langile IDa")
    izena = fields.Char(string="Izena")
    abizena = fields.Char(string="Abizena")
    email = fields.Char(string="Emaila")
    pasahitza = fields.Char(string="Pasahitza", groups="base.group_system", password=True)
    nivel_permisos = fields.Selection([('admin', 'Administratzailea'), ('user', 'Erabiltzailea')], string="Baimen Maila", groups="base.group_system")
    txat_permiso = fields.Boolean(string="Txat Baimena", groups="base.group_system")
    created_at = fields.Datetime(string="Sortze Data")
    updated_at = fields.Datetime(string="Eguneratze Data")
    deleted_at = fields.Datetime(string="Ezabatze Data")

    def name_get(self):
        _logger.debug(f"Calling name_get for Zerbitzaria: {self}")
        result = []
        for record in self:
            name = f"{record.izena or ''} {record.abizena or ''}".strip()
            if not name:
                name = record.worker_id or "Unknown"
            result.append((record.id, name))
        return result

    # Resto del código del modelo (constraints, create, sincronizar_datos, etc.)

    @api.constrains('worker_id')
    def _check_worker_id_unique(self):
        for record in self:
            if self.search_count([('worker_id', '=', record.worker_id), ('id', '!=', record.id)]):
                raise ValidationError(_('El ID Langilea debe ser único.'))

    @api.constrains('email')
    def _check_email_format(self):
        import re
        for record in self:
            if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', record.email):
                raise ValidationError(_('El formato del email no es válido: %s') % record.email)

    @api.model
    def create(self, vals):
        # Validar que los campos requeridos no estén vacíos
        required_fields = ['izena', 'abizena', 'pasahitza', 'email']
        missing_fields = [field for field in required_fields if not vals.get(field)]
        if missing_fields:
            raise ValidationError(_('Faltan campos requeridos: %s') % ', '.join(missing_fields))

        # Crear el registro en Odoo
        record = super(Zerbitzaria, self).create(vals)

        # Preparar los datos para enviar a la API, incluyendo worker_id si está definido
        worker_data = {
            'worker_id': record.worker_id,
            'izena': record.izena,
            'abizena': record.abizena,
            'pasahitza': record.pasahitza,
            'email': record.email,
            'nivel_Permisos': record.nivel_Permisos,
            'txat_permiso': record.txat_permiso,
            'created_at': record.created_at and record.created_at.strftime('%Y-%m-%d %H:%M:%S') or None,
            'updated_at': record.updated_at and record.updated_at.strftime('%Y-%m-%d %H:%M:%S') or None,
            'deleted_at': record.deleted_at and record.deleted_at.strftime('%Y-%m-%d %H:%M:%S') or None,
        }

        # Log de los datos enviados para depuración
        _logger.info(f"Datos enviados a la API (create): {worker_data}")

        # Enviar los datos a la API externa
        try:
            api_url = "http://192.168.115.188:80/zerbitzariak_konexioa.php"
            headers = {'Content-Type': 'application/json'}
            response = requests.post(api_url, json=worker_data, headers=headers)
            response.raise_for_status()
            response_data = response.json()

            if response.status_code in (200, 201):
                # Solo actualizar worker_id si no se ingresó manualmente
                if 'worker_id' in response_data and not vals.get('worker_id'):
                    record.write({'worker_id': response_data['worker_id']})
                    _logger.info(f"Trabajador con email {record.email} creado en MySQL con worker_id {response_data['worker_id']}.")
                else:
                    _logger.info(f"Trabajador con email {record.email} creado en MySQL, usando worker_id manual {record.worker_id}.")
            else:
                _logger.error(f"Error al crear trabajador en la API: {response.status_code} - {response.text}")
                raise UserError(_("No se pudo sincronizar el trabajador con la base de datos externa: %s") % response.text)

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error de conexión con la API: {str(e)}")
            raise UserError(_("Error de conexión al intentar sincronizar el trabajador con la base de datos externa: %s") % str(e))

        return record

    def sincronizar_datos(self):
        try:
            # Obtener los datos de la API
            api_url = "http://192.168.115.188:80/zerbitzariak_konexioa.php"
            response = requests.get(api_url)
            response.raise_for_status()

            if not response.text.strip():
                raise UserError(_("La API devolvió una respuesta vacía."))

            try:
                data = response.json()
            except ValueError as e:
                _logger.error(f"Error al parsear JSON: {str(e)} - Respuesta: {response.text}")
                raise UserError(_("Error al parsear la respuesta de la API: %s - Respuesta: %s") % (str(e), response.text))

            if data['status_code'] != 200:
                raise UserError(_("Error al obtener los datos de los trabajadores: %s") % data.get('mezua', 'Error desconocido'))

            langileak = data.get('langileak', [])
            created_count = 0
            updated_count = 0
            skipped_count = 0

            # Expresión regular para validar emails
            import re
            email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

            for langilea in langileak:
                email = langilea.get('email', '')
                izena = langilea.get('izena', '')
                abizena = langilea.get('abizena', '')  # Abizena es opcional

                # Validar campos requeridos (solo izena)
                if not izena:
                    _logger.warning(f"Saltando trabajador con 'izena' vacío: {langilea}")
                    skipped_count += 1
                    continue

                # Manejar email inválido asignando un valor por defecto
                if not email or not re.match(email_pattern, email):
                    original_email = email
                    email = f"invalid_email_{langilea.get('id', 'unknown')}@example.com"
                    _logger.warning(f"Email inválido o vacío detectado: '{original_email}'. Usando email por defecto: {email} - Datos: {langilea}")

                worker = self.search([('email', '=', email)], limit=1)
                # Mapear nivel_Permisos de entero a valor del Selection
                nivel_permisos = 'user' if langilea.get('nivel_Permisos', 0) == 0 else 'admin'
                worker_data = {
                    'izena': izena,
                    'abizena': abizena if abizena else None,  # Usar None para JSON
                    'email': email,
                    'nivel_permisos': nivel_permisos,  # Usar el nombre del campo correcto
                    'txat_permiso': langilea.get('txat_permiso', True),  # Asegurar formato booleano
                    'created_at': langilea.get('created_at'),
                    'updated_at': langilea.get('updated_at'),
                    'deleted_at': langilea.get('deleted_at'),
                }

                try:
                    api_url_post = "http://192.168.115.188:80/zerbitzariak_konexioa.php"
                    worker_data_to_send = worker_data.copy()
                    worker_data_to_send['pasahitza'] = 'default_password' if not worker else (worker.pasahitza or 'default_password')
                    if worker and worker.worker_id:
                        worker_data_to_send['worker_id'] = int(worker.worker_id)
                    else:
                        worker_data_to_send['worker_id'] = int(langilea.get('id', 0))

                    # Asegurar que los valores sean compatibles con JSON
                    worker_data_to_send['created_at'] = worker_data_to_send['created_at'] or None
                    worker_data_to_send['updated_at'] = worker_data_to_send['updated_at'] or None
                    worker_data_to_send['deleted_at'] = worker_data_to_send['deleted_at'] or None
                    worker_data_to_send['txat_permiso'] = bool(worker_data_to_send['txat_permiso'])  # Asegurar booleano

                    # Enviar como JSON
                    _logger.info(f"Datos enviados a la API (POST): {worker_data_to_send}")
                    response_post = requests.post(api_url_post, json=worker_data_to_send)
                    response_post.raise_for_status()
                    try:
                        response_data = response_post.json()
                    except ValueError:
                        response_data = {'error': response_post.text}

                    if response_post.status_code not in (200, 201):
                        _logger.error(f"Error al sincronizar el trabajador con la base de datos externa: {response_data}")
                        raise UserError(_("No se pudo sincronizar el trabajador con la base de datos externa: %s") % response_data.get('error', 'Error desconocido'))

                    if 'worker_id' in response_data and (not worker or not worker.worker_id):
                        worker_data['worker_id'] = str(response_data['worker_id'])
                    else:
                        worker_data['worker_id'] = worker.worker_id if worker else str(response_data.get('worker_id'))

                except requests.exceptions.RequestException as e:
                    _logger.error(f"Error al enviar datos a la API externa: {str(e)} - Respuesta: {response_post.text if 'response_post' in locals() else 'Sin respuesta'}")
                    raise UserError(_("Error al sincronizar el trabajador con la base de datos externa: %s - Respuesta: %s") % (str(e), response_post.text if 'response_post' in locals() else 'Sin respuesta'))

                try:
                    if worker:
                        worker.write(worker_data)
                        _logger.info(f"Trabajador con email {email} actualizado en Odoo.")
                        updated_count += 1
                    else:
                        worker_data['pasahitza'] = 'default_password'
                        self.create(worker_data)
                        _logger.info(f"Trabajador con email {email} creado en Odoo.")
                        created_count += 1
                except Exception as e:
                    _logger.error(f"Error al crear/actualizar trabajador en Odoo: {str(e)} - Datos: {worker_data}")
                    skipped_count += 1
                    continue

            message = f"{created_count} langile berri | {updated_count} eguneratu"
            if skipped_count > 0:
                message += f" | {skipped_count} saltados por datos inválidos"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_("Error al sincronizar los trabajadores: %s") % str(e))
        except Exception as e:
            _logger.error(f"Error inesperado en sincronizar_datos: {str(e)}")
            raise UserError(_("Error inesperado al sincronizar los trabajadores: %s") % str(e))


    def sincronizar_registro_individual(self, email=None):
        """Sincroniza un trabajador específico desde la API externa usando su email."""
        if not email and self:
            email = self.email
        if not email:
            raise UserError(_("Emaila beharrezkoa da langilea sinkronizatzeko."))

        try:
            api_url = f"http://192.168.115.188:80/zerbitzariak_konexioa.php?email={email}"
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data['status_code'] == 404:
                raise UserError(_("Trabajador no encontrado: %s") % data.get('mezua', 'Email no encontrado'))
            elif data['status_code'] != 200:
                raise UserError(_("Error al obtener los datos del trabajador: %s") % data.get('mezua', 'Error desconocido'))

            langilea = data.get('langilea', {})
            worker = self.search([('email', '=', langilea['email'])], limit=1)
            worker_data = {
                'izena': langilea['izena'],
                'abizena': langilea['abizena'],
                'email': langilea['email'],
                'nivel_Permisos': langilea['nivel_Permisos'],
                'txat_permiso': langilea['txat_permiso'],
                'created_at': langilea['created_at'],
                'updated_at': langilea['updated_at'],
                'deleted_at': langilea['deleted_at'],
            }

            # Enviar los datos a la API externa para crear o actualizar en MySQL
            try:
                api_url_post = "http://192.168.115.188:80/zerbitzariak_konexioa.php"
                worker_data_to_send = worker_data.copy()
                worker_data_to_send['pasahitza'] = 'default_password' if not worker else worker.pasahitza
                # Incluir worker_id si ya existe en el registro
                if worker and worker.worker_id:
                    worker_data_to_send['worker_id'] = worker.worker_id
                response_post = requests.post(api_url_post, json=worker_data_to_send)
                response_post.raise_for_status()
                response_data = response_post.json()

                if response_post.status_code not in (200, 201):
                    _logger.error(f"Error al sincronizar el trabajador con la base de datos externa: {response_data}")
                    raise UserError(_("No se pudo sincronizar el trabajador con la base de datos externa: %s") % response_data.get('error', 'Error desconocido'))

                # Actualizar worker_id solo si no tiene un valor manual
                if 'worker_id' in response_data and (not worker or not worker.worker_id):
                    worker_data['worker_id'] = response_data['worker_id']
                else:
                    worker_data['worker_id'] = worker.worker_id if worker else response_data.get('worker_id')

            except requests.exceptions.RequestException as e:
                _logger.error(f"Error al enviar datos a la API externa: {str(e)}")
                raise UserError(_("Error al sincronizar el trabajador con la base de datos externa: %s") % str(e))

            # Actualizar o crear el trabajador en Odoo
            if worker:
                worker.write(worker_data)
                _logger.info(f"Trabajador con email {langilea['email']} actualizado en Odoo.")
            else:
                worker_data['pasahitza'] = 'default_password'
                self.create(worker_data)
                _logger.info(f"Trabajador con email {langilea['email']} creado en Odoo.")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Eguneratua!',
                    'message': f"Trabajador con email {email} eguneratu da",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_("Error al sincronizar el trabajador: %s") % str(e))

class Eskaera(models.Model):
    _name = 'jatetxeko_estatistikak.eskaera'
    _description = 'Eskaera'

    external_ref = fields.Integer(string="ID Externo")
    langilea_id = fields.Many2one('jatetxeko_estatistikak.zerbitzaria', string="Langilea")
    langilea_worker_id = fields.Integer(string="ID Langilea")
    mahaia_id = fields.Many2one('jatetxeko_estatistikak.mahaia', string="Mahaia")
    status = fields.Char(string="Egoera")
    done = fields.Boolean(string="Eginda")
    EskaeraDone = fields.Boolean(string="Eskaera Eginda")
    ordainduta = fields.Boolean(string="Ordainduta")

    @api.depends('langilea_id', 'langilea_id.worker_id')
    def _compute_langilea_worker_id(self):
        for record in self:
            record.langilea_worker_id = record.langilea_id.worker_id if record.langilea_id else False

    def sincronizar_eskaerak(self):
        try:
            # Sincronizar los camareros primero
            Zerbitzaria = self.env['jatetxeko_estatistikak.zerbitzaria']
            Zerbitzaria.sincronizar_datos()

            # Obtener todos los pedidos desde la API
            url = "http://192.168.115.188:80/eskaera_konexioa.php"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get('status_code') == 200 and 'eskaerak' in result:
                Eskaera = self.env['jatetxeko_estatistikak.eskaera']
                created_count = 0
                updated_count = 0

                for eskaria in result['eskaerak']:
                    if not eskaria.get('id'):
                        _logger.warning(f"Eskaera sin ID. Saltando: {eskaria}")
                        continue

                    existing = Eskaera.search([('external_ref', '=', str(eskaria.get('id')))], limit=1)

                    # Buscar el camarero por worker_id
                    langilea = False
                    langilea_id = eskaria.get('langilea_id')
                    if langilea_id:
                        langilea = self.env['jatetxeko_estatistikak.zerbitzaria'].search(
                            [('worker_id', '=', str(langilea_id))], limit=1)
                        if not langilea:
                            _logger.warning(f"No se encontró Zerbitzaria para langilea_id {langilea_id}. Datos de la eskaera: {eskaria}")
                        else:
                            _logger.info(f"Zerbitzaria encontrado para langilea_id {langilea_id}: {langilea.name_get()[0][1]} (worker_id={langilea.worker_id})")

                    # Buscar la mesa por zenbakia
                    mahaia = False
                    mahaia_id = eskaria.get('mahaila_id')
                    if mahaia_id:
                        mahaia = self.env['jatetxeko_estatistikak.mahaia'].search(
                            [('zenbakia', '=', int(mahaia_id))], limit=1)
                        if not mahaia:
                            _logger.warning(f"No se encontró Mahaia con zenbakia {mahaia_id}.")

                    vals = {
                        'external_ref': str(eskaria.get('id')),
                        'langilea_id': langilea.id if langilea else False,
                        'mahaia_id': mahaia.id if mahaia else False,
                        'status': str(eskaria.get('egoera', '0')),
                        'done': bool(eskaria.get('done', False)),
                        'EskaeraDone': bool(eskaria.get('EskaeraDone', False)),
                        'ordainduta': bool(eskaria.get('ordainduta', False)),
                    }

                    if existing:
                        existing.write(vals)
                        updated_count += 1
                    else:
                        Eskaera.create(vals)
                        created_count += 1

                # Actualizar las estadísticas de pedidos por camarero después de sincronizar
                ZerbitzariPedidos = self.env['jatetxeko_estatistikak.zerbitzari_pedidos']
                ZerbitzariPedidos.sincronizar_zerbitzari_pedidos()

                message = f"{created_count} eskaera berri | {updated_count} eguneratu"
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sinkronizazioa'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_(result.get('mezua', 'Datu basean errorea')))

        except Exception as e:
            error_msg = _('Errorea eskaerak sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)
    
    def sincronizar_eskaera_bakarra(self):
        try:
            if not self.external_ref:
                raise UserError(_("Eskaerak ez du IDrik"))
            
            api_url = f"http://192.168.115.188:80/eskaera_konexioa.php?id={self.external_ref}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status_code') == 200 and 'eskaera' in data:
                    langilea = False
                    langilea_id = data['eskaera'].get('langilea_id')
                    if langilea_id:
                        langilea = self.env['jatetxeko_estatistikak.zerbitzaria'].search(
                            [('worker_id', '=', str(langilea_id))], limit=1)
                    
                    mahaia = False
                    mahaia_id = data['eskaera'].get('mahaila_id')
                    if mahaia_id:
                        mahaia = self.env['jatetxeko_estatistikak.mahaia'].search(
                            [('zenbakia', '=', int(mahaia_id))], limit=1)
                    
                    self.write({
                        'external_ref': str(data['eskaera'].get('id')),
                        'langilea_id': langilea.id if langilea else False,
                        'mahaia_id': mahaia.id if mahaia else False,
                        'status': str(data['eskaera'].get('egoera', self.status)),
                        'done': bool(data['eskaera'].get('done', self.done)),
                        'EskaeraDone': bool(data['eskaera'].get('EskaeraDone', self.EskaeraDone)),
                        'ordainduta': bool(data['eskaera'].get('ordainduta', self.ordainduta)),
                    })
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Eguneratua!',
                            'message': f"{self.external_ref} eskaera eguneratu da",
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    raise UserError(data.get('mezua', 'Datuak ez dira zuzenak'))
            else:
                raise UserError(f"Errorea HTTP {response.status_code}")
                
        except Exception as e:
            raise UserError(f"Errorea eskaera sinkronizatzerakoan: {str(e)}")
        
class Mahaia(models.Model):
    _name = 'jatetxeko_estatistikak.mahaia'
    _description = 'Mahaia'

    zenbakia = fields.Integer(string="Mahaia Zenbakia", required=True)
    eserlekuak = fields.Integer(string="Eserlekuak")
    habilitado = fields.Boolean(string="Habilitado")
    terraza = fields.Boolean(string="Terraza")
    updated_at = fields.Datetime(string="Última actualización")

    @api.constrains('zenbakia')
    def _check_zenbakia_unique(self):
        for record in self:
            if self.search_count([('zenbakia', '=', record.zenbakia), ('id', '!=', record.id)]):
                raise ValidationError(_('El número de la mesa debe ser único.'))

    def name_get(self):
        _logger.debug(f"Calling name_get for Mahaia: {self}")
        result = []
        for record in self:
            name = str(record.zenbakia)
            result.append((record.id, name))
        return result

    def sincronizar_guztiak_mahaiak(self):
        try:
            url = "http://192.168.115.188:80/mahaiak_konexioa.php"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get('status_code') == 200 and 'mahaia' in result:
                Mahaia = self.env['jatetxeko_estatistikak.mahaia']
                created_count = 0
                updated_count = 0

                for mahaia in result['mahaia']:
                    mahaia_id = mahaia.get('id')
                    if not mahaia_id:
                        _logger.warning(f"Mahaia sin ID. Saltando: {mahaia}")
                        continue

                    existing = Mahaia.search([('zenbakia', '=', int(mahaia_id))], limit=1)

                    # Convertir terraza a booleano (0 → False, cualquier otro valor → True)
                    terraza_value = mahaia.get('terraza', 0)
                    terraza_bool = False if terraza_value == 0 else True

                    # Parsear updated_at desde el formato ISO 8601
                    updated_at = mahaia.get('updated_at')
                    if updated_at:
                        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        updated_at = updated_at.replace(tzinfo=None)
                    else:
                        updated_at = fields.Datetime.now()

                    vals = {
                        'zenbakia': int(mahaia_id),
                        'eserlekuak': mahaia.get('eserlekuak', 0),
                        'habilitado': mahaia.get('habilitado', True),
                        'terraza': terraza_bool,
                        'updated_at': updated_at,
                    }

                    if existing:
                        existing.write(vals)
                        updated_count += 1
                    else:
                        Mahaia.create(vals)
                        created_count += 1

                message = f"{created_count} mahaia berri | {updated_count} eguneratu"
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sinkronizazioa'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_(result.get('mezua', 'Datu basean errorea')))

        except Exception as e:
            error_msg = _('Errorea mahaiak sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

    def sincronizar_mahaia(self):
        try:
            if not self.zenbakia:
                raise UserError(_("Mahiak ez du Zenbakirik"))

            api_url = f"http://192.168.115.188:80/mahaiak_konexioa.php?id={self.zenbakia}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('status_code') == 200 and 'mahaia' in data:
                mahaia = data['mahaia']

                # Convertir terraza a booleano
                terraza_value = mahaia.get('terraza', 0)
                terraza_bool = False if terraza_value == 0 else True

                # Parsear updated_at desde el formato ISO 8601
                updated_at = mahaia.get('updated_at')
                if updated_at:
                    updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    updated_at = updated_at.replace(tzinfo=None)
                else:
                    updated_at = fields.Datetime.now()

                self.write({
                    'zenbakia': int(mahaia.get('id')),
                    'eserlekuak': mahaia.get('eserlekuak', 0),
                    'habilitado': mahaia.get('habilitado', True),
                    'terraza': terraza_bool,
                    'updated_at': updated_at,
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Eguneratua!',
                        'message': f"{self.zenbakia} mahaia eguneratu da",
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(data.get('mezua', 'Datuak ez dira zuzenak'))

        except Exception as e:
            raise UserError(f"Errorea mahaia sinkronizatzerakoan: {str(e)}")

    @api.model
    def create(self, vals):
        # Crear el registro en Odoo
        record = super(Mahaia, self).create(vals)

        # Verificar si la mesa ya existe en la API externa
        try:
            check_url = f"http://192.168.115.188:80/mahaiak_konexioa.php?id={record.zenbakia}"
            response = requests.get(check_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Si la mesa ya existe en la API externa, no intentamos crearla
            if data.get('status_code') == 200 and 'mahaia' in data:
                _logger.info(f"Mesa {record.zenbakia} ya existe en la base de datos externa. No se creará de nuevo.")
                return record  # Salimos del método sin intentar crear en la API

        except requests.exceptions.RequestException as e:
            _logger.warning(f"Error al verificar si la mesa {record.zenbakia} existe en la API: {str(e)}")
            # Continuamos con la creación en la API, pero podríamos manejar esto de manera diferente si es necesario

        # Preparar los datos para enviar a la API
        table_data = {
            'zenbakia': record.zenbakia,
            'eserlekuak': record.eserlekuak,
            'habilitado': record.habilitado,
            'terraza': record.terraza,
            'updated_at': record.updated_at and record.updated_at.strftime('%Y-%m-%d %H:%M:%S') or None,
        }

        # Enviar los datos a la API externa
        try:
            api_url = "http://192.168.115.188:80/api_mahaia.php"
            headers = {
                'Content-Type': 'application/json',
            }
            response = requests.post(api_url, json=table_data, headers=headers)

            if response.status_code == 201:  # Código para "creado"
                _logger.info(f"Mesa {record.zenbakia} creada exitosamente en la base de datos externa.")
            else:
                _logger.error(f"Error al crear mesa en la API: {response.status_code} - {response.text}")
                raise UserError(
                    _("No se pudo sincronizar la mesa con la base de datos externa: %s") % response.text
                )

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error de conexión con la API: {str(e)}")
            raise UserError(
                _("Error de conexión al intentar sincronizar la mesa con la base de datos externa: %s") % str(e)
            )

        return record

class Platera(models.Model):
    _name = 'jatetxeko_estatistikak.platera'
    _description = 'Platera'

    external_id = fields.Integer(string="ID Externo")
    izena = fields.Char(string="Izena")
    deskribapena = fields.Char(string="Deskribapena")
    mota = fields.Char(string="Mota")
    platera_mota = fields.Char(string="Platera Mota")
    prezioa = fields.Float(string="Prezioa")
    menu = fields.Char(string="Menu")
    created_at = fields.Datetime(string="Sortze Data")
    created_by = fields.Char(string="Sortzailea")
    updated_at = fields.Datetime(string="Eguneratze Data")
    updated_by = fields.Char(string="Eguneratzailea")
    deleted_at = fields.Datetime(string="Ezabatze Data")
    deleted_by = fields.Char(string="Ezabatzailea")

    @api.constrains('external_id')
    def _check_external_id_unique(self):
        for record in self:
            if record.external_id and self.search_count([('external_id', '=', record.external_id), ('id', '!=', record.id)]):
                raise ValidationError(_('El ID Externo debe ser único.'))

    def parse_date(self, date_str):
        if not date_str:
            return False
        try:
            return datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                _logger.warning(f"No se pudo parsear la fecha: {date_str}")
                return fields.Datetime.now()

    def sincronizar_guztiak_platerak(self):
        try:
            url = "http://192.168.115.188:80/platera_konexioa.php"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Log de la respuesta completa para depuración
            _logger.debug("Respuesta de platera_konexioa.php: %s", response.text)

            result = response.json()
            _logger.debug("Resultado parseado: %s", result)

            # Si result es una lista, asumimos que es la lista de platos directamente
            if isinstance(result, list):
                platerak = result
            else:
                # Si es un diccionario, verificamos las claves esperadas
                if result.get('status_code') != 200:
                    raise UserError(_(result.get('mezua', 'Datu basean errorea')))
                if 'platerak' not in result:
                    raise UserError(_("Ez dago 'platerak' eremurik APIaren erantzunean"))
                platerak = result['platerak']

            Platera = self.env['jatetxeko_estatistikak.platera']
            created_count = 0
            updated_count = 0

            for platera in platerak:
                external_id = platera.get('id')
                if not external_id:
                    _logger.warning(f"Platera sin ID. Saltando: {platera}")
                    continue

                existing = Platera.search([('external_id', '=', str(external_id))], limit=1)

                vals = {
                    'external_id': str(external_id),
                    'izena': platera.get('izena', ''),
                    'deskribapena': platera.get('deskribapena', ''),
                    'mota': platera.get('mota', ''),
                    'platera_mota': platera.get('platera_mota', ''),
                    'prezioa': float(platera.get('prezioa', 0.0)),
                    'menu': bool(int(platera.get('menu', 0))),
                    'created_at': self.parse_date(platera.get('created_at')),
                    'created_by': str(platera.get('created_by', '')),
                    'updated_at': self.parse_date(platera.get('updated_at')),
                    'updated_by': str(platera.get('updated_by', '')),
                    'deleted_at': self.parse_date(platera.get('deleted_at')),
                    'deleted_by': str(platera.get('deleted_by', '')),
                }

                if existing:
                    existing.write(vals)
                    updated_count += 1
                else:
                    Platera.create(vals)
                    created_count += 1

            message = f"{created_count} platera berri | {updated_count} eguneratu"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = _('Errorea platerak sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

    def sincronizar_platera(self):
        try:
            if not self.external_id:
                raise UserError(_("Platerak ez du IDrik"))

            api_url = f"http://192.168.115.188:80/platera_konexioa.php?id={self.external_id}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()

            # Log de la respuesta completa para depuración
            _logger.debug("Respuesta de platera_konexioa.php (individual): %s", response.text)

            result = response.json()
            _logger.debug("Resultado parseado (individual): %s", result)

            # Como la API devuelve una lista, buscamos el plato con el ID correspondiente
            platera = None
            if isinstance(result, list):
                for item in result:
                    if str(item.get('id')) == str(self.external_id):
                        platera = item
                        break
                if not platera:
                    raise UserError(_("Ez da platerarik aurkitu ID honekin: %s") % self.external_id)
            else:
                if result.get('status_code') != 200:
                    raise UserError(_(result.get('mezua', 'Datuak ez dira zuzenak')))
                if 'platera' not in result:
                    raise UserError(_("Ez dago 'platera' eremurik APIaren erantzunean"))
                platera = result['platera']

            self.write({
                'external_id': str(platera.get('id')),
                'izena': platera.get('izena', ''),
                'deskribapena': platera.get('deskribapena', ''),
                'mota': platera.get('mota', ''),
                'platera_mota': platera.get('platera_mota', ''),
                'prezioa': float(platera.get('prezioa', 0.0)),
                'menu': bool(int(platera.get('menu', 0))),
                'created_at': self.parse_date(platera.get('created_at')),
                'created_by': str(platera.get('created_by', '')),
                'updated_at': self.parse_date(platera.get('updated_at')),
                'updated_by': str(platera.get('updated_by', '')),
                'deleted_at': self.parse_date(platera.get('deleted_at')),
                'deleted_by': str(platera.get('deleted_by', '')),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Eguneratua!',
                    'message': f"{self.external_id} platera eguneratu da",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(f"Errorea platera sinkronizatzerakoan: {str(e)}")
        
class PlateraCantidad(models.Model):
    _name = 'jatetxeko_estatistikak.plateracant'
    _description = 'Platos Más Pedidos'
    _rec_name = 'plato_nombre'
    _order = 'cantidad_pedidos desc'

    plato_id = fields.Integer(string="Plato ID", readonly=True)
    plato_nombre = fields.Char(string="Nombre del Plato", readonly=True)
    cantidad_pedidos = fields.Integer(string="Cantidad de Pedidos", readonly=True)

    def sincronizar_plateracant(self):
        try:
            url = "http://192.168.115.188:80/plateracant_konexioa.php"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            _logger.debug("Respuesta de plateracant_konexioa.php: %s", response.text)

            result = response.json()
            _logger.debug("Resultado parseado: %s", result)

            if result.get('status_code') != 200:
                raise UserError(_(result.get('mezua', 'Datu basean errorea')))
            if 'plateracant' not in result:
                raise UserError(_("Ez dago 'plateracant' eremurik APIaren erantzunean"))

            plateracant = result['plateracant']
            PlateraCantidad = self.env['jatetxeko_estatistikak.plateracant']

            # Limpiar los datos existentes antes de sincronizar
            PlateraCantidad.search([]).unlink()

            created_count = 0
            for item in plateracant:
                vals = {
                    'plato_id': item.get('plato_id', 0),
                    'plato_nombre': item.get('plato_nombre', ''),
                    'cantidad_pedidos': item.get('cantidad_pedidos', 0),
                }
                PlateraCantidad.create(vals)
                created_count += 1

            # Mostrar notificación de éxito
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': f"{created_count} platera kantitate eguneratu",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = _('Errorea plateracant sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)
        
class ZerbitzariPedidos(models.Model):
    _name = 'jatetxeko_estatistikak.zerbitzari_pedidos'
    _description = 'Pedidos por Zerbitzari'
    _rec_name = 'zerbitzari_nombre'
    _order = 'cantidad_pedidos desc'

    zerbitzari_id = fields.Integer(string="Zerbitzari ID", readonly=True)
    zerbitzari_nombre = fields.Char(string="Nombre del Zerbitzari", readonly=True)
    cantidad_pedidos = fields.Integer(string="Cantidad de Pedidos", readonly=True)

    def sincronizar_zerbitzari_pedidos(self):
        try:
            # Obtener todos los pedidos
            Eskaera = self.env['jatetxeko_estatistikak.eskaera']
            pedidos = Eskaera.search([])
            _logger.info(f"Total de pedidos encontrados: {len(pedidos)}")
    
            # Obtener todos los camareros
            Zerbitzaria = self.env['jatetxeko_estatistikak.zerbitzaria']
            zerbitzariak = Zerbitzaria.search([])
            _logger.info(f"Total de zerbitzariak encontrados: {len(zerbitzariak)}")
    
            # Crear un diccionario para contar los pedidos por camarero
            pedidos_por_zerbitzari = {}
            for zerbitzari in zerbitzariak:
                try:
                    nombre = zerbitzari.name_get()[0][1] if zerbitzari.name_get() else (zerbitzari.worker_id or "Unknown")
                except Exception as e:
                    _logger.error(f"Error al obtener el nombre de zerbitzari {zerbitzari.id}: {str(e)}")
                    nombre = zerbitzari.worker_id or "Unknown"
    
                pedidos_por_zerbitzari[zerbitzari.id] = {
                    'nombre': nombre,
                    'worker_id': zerbitzari.worker_id,
                    'cantidad': 0
                }
                _logger.info(f"Zerbitzaria añadido al conteo: ID={zerbitzari.id}, worker_id={zerbitzari.worker_id}, nombre={nombre}")
    
            # Contar los pedidos por camarero
            for pedido in pedidos:
                if pedido.langilea_id:
                    if pedido.langilea_id.id in pedidos_por_zerbitzari:
                        pedidos_por_zerbitzari[pedido.langilea_id.id]['cantidad'] += 1
                        _logger.debug(f"Pedido {pedido.id} asignado a zerbitzari ID={pedido.langilea_id.id} (worker_id={pedido.langilea_id.worker_id})")
                    else:
                        _logger.warning(f"Pedido {pedido.id} tiene langilea_id {pedido.langilea_id.id}, pero no está en pedidos_por_zerbitzari")
                else:
                    _logger.warning(f"Pedido {pedido.id} no tiene langilea_id asignado")
    
            # Limpiar los datos existentes antes de sincronizar
            ZerbitzariPedidos = self.env['jatetxeko_estatistikak.zerbitzari_pedidos']
            ZerbitzariPedidos.search([]).unlink()
    
            # Crear nuevos registros con los datos calculados
            created_count = 0
            for zerbitzari_id, data in pedidos_por_zerbitzari.items():
                if data['cantidad'] > 0:  # Solo incluir camareros con pedidos
                    vals = {
                        'zerbitzari_id': zerbitzari_id,
                        'zerbitzari_nombre': data['nombre'],
                        'cantidad_pedidos': data['cantidad'],
                    }
                    ZerbitzariPedidos.create(vals)
                    created_count += 1
                    _logger.info(f"Zerbitzari ID={zerbitzari_id} (worker_id={data['worker_id']}, nombre={data['nombre']}) tiene {data['cantidad']} pedidos")
    
            # Mostrar notificación de éxito
            return {
                'Coords': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': f"{created_count} zerbitzarien datuak eguneratu dira",
                    'type': 'success',
                    'sticky': False,
                }
            }
    
        except Exception as e:
            error_msg = _('Errorea zerbitzarien pedidos sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

class PedidosDiaSemana(models.Model):
    _name = 'jatetxeko_estatistikak.pedidos_dia_semana'
    _description = 'Pedidos por Día de la Semana'
    _rec_name = 'dia_semana'
    _order = 'cantidad_pedidos desc'

    dia_semana = fields.Char(string="Día de la Semana", readonly=True)
    cantidad_pedidos = fields.Integer(string="Cantidad de Pedidos", readonly=True)

    def sincronizar_pedidos_dia_semana(self):
        try:
            # Obtener todos los pedidos
            Eskaera = self.env['jatetxeko_estatistikak.eskaera']
            pedidos = Eskaera.search([])

            # Diccionario para mapear números de día a nombres
            dias_semana = {
                0: "Lunes",
                1: "Martes",
                2: "Miércoles",
                3: "Jueves",
                4: "Viernes",
                5: "Sábado",
                6: "Domingo",
            }

            # Contar pedidos por día de la semana
            pedidos_por_dia = {dia: 0 for dia in dias_semana.values()}
            for pedido in pedidos:
                if pedido.create_date:
                    dia_numero = pedido.create_date.weekday()  # 0 = Lunes, 6 = Domingo
                    dia_nombre = dias_semana[dia_numero]
                    pedidos_por_dia[dia_nombre] += 1

            # Limpiar los datos existentes antes de sincronizar
            PedidosDiaSemana = self.env['jatetxeko_estatistikak.pedidos_dia_semana']
            PedidosDiaSemana.search([]).unlink()

            # Crear nuevos registros con los datos calculados
            created_count = 0
            for dia, cantidad in pedidos_por_dia.items():
                vals = {
                    'dia_semana': dia,
                    'cantidad_pedidos': cantidad,
                }
                PedidosDiaSemana.create(vals)
                created_count += 1

            # Mostrar notificación de éxito
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': f"{created_count} días de la semana actualizados con datos de pedidos",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = _('Errorea pedidos por día de la semana sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

class FacturacionDiaSemana(models.Model):
    _name = 'jatetxeko_estatistikak.facturacion_dia_semana'
    _description = 'Facturación por Día de la Semana'
    _rec_name = 'dia_semana'
    _order = 'total_facturado desc'

    dia_semana = fields.Char(string="Día de la Semana", readonly=True)
    total_facturado = fields.Integer(string="Total Facturado", readonly=True)
    pedidos_facturados = fields.Integer(string="Pedidos Facturados", readonly=True)

    def sincronizar_facturacion_dia_semana(self):
        try:
            # Obtener todos los pedidos pagados (ordainduta=True)
            Eskaera = self.env['jatetxeko_estatistikak.eskaera']
            pedidos = Eskaera.search([('ordainduta', '=', True)])

            # Diccionario para mapear números de día a nombres
            dias_semana = {
                0: "Lunes",
                1: "Martes",
                2: "Miércoles",
                3: "Jueves",
                4: "Viernes",
                5: "Sábado",
                6: "Domingo",
            }

            # Contar pedidos facturados por día de la semana
            facturacion_por_dia = {dia: {'total': 0, 'pedidos': 0} for dia in dias_semana.values()}
            for pedido in pedidos:
                if pedido.create_date:
                    dia_numero = pedido.create_date.weekday()  # 0 = Lunes, 6 = Domingo
                    dia_nombre = dias_semana[dia_numero]
                    facturacion_por_dia[dia_nombre]['pedidos'] += 1
                    facturacion_por_dia[dia_nombre]['total'] += 1  # Reemplaza con el campo real si existe

            # Limpiar los datos existentes antes de sincronizar
            FacturacionDiaSemana = self.env['jatetxeko_estatistikak.facturacion_dia_semana']
            FacturacionDiaSemana.search([]).unlink()

            # Crear nuevos registros con los datos calculados
            created_count = 0
            for dia, datos in facturacion_por_dia.items():
                vals = {
                    'dia_semana': dia,
                    'total_facturado': datos['total'],
                    'pedidos_facturados': datos['pedidos'],
                }
                FacturacionDiaSemana.create(vals)
                created_count += 1

            # Mostrar notificación de éxito
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': f"{created_count} días de la semana actualizados con datos de facturación",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = _('Errorea facturación por día de la semana sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

class PedidosDiaMes(models.Model):
    _name = 'jatetxeko_estatistikak.pedidos_dia_mes'
    _description = 'Pedidos por Día del Mes'
    _rec_name = 'dia_mes'
    _order = 'cantidad_pedidos desc'

    dia_mes = fields.Integer(string="Día del Mes", readonly=True)
    cantidad_pedidos = fields.Integer(string="Cantidad de Pedidos", readonly=True)

    def sincronizar_pedidos_dia_mes(self):
        try:
            # Obtener todos los pedidos
            Eskaera = self.env['jatetxeko_estatistikak.eskaera']
            pedidos = Eskaera.search([])

            # Contar pedidos por día del mes (1 al 31)
            pedidos_por_dia = {dia: 0 for dia in range(1, 32)}  # Días del 1 al 31
            for pedido in pedidos:
                if pedido.create_date:
                    dia = pedido.create_date.day  # Día del mes (1 al 31)
                    pedidos_por_dia[dia] += 1

            # Limpiar los datos existentes antes de sincronizar
            PedidosDiaMes = self.env['jatetxeko_estatistikak.pedidos_dia_mes']
            PedidosDiaMes.search([]).unlink()

            # Crear nuevos registros con los datos calculados
            created_count = 0
            for dia, cantidad in pedidos_por_dia.items():
                vals = {
                    'dia_mes': dia,
                    'cantidad_pedidos': cantidad,
                }
                PedidosDiaMes.create(vals)
                created_count += 1

            # Mostrar notificación de éxito
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronizazioa'),
                    'message': f"{created_count} días del mes actualizados con datos de pedidos",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = _('Errorea pedidos por día del mes sinkronizatzerakoan: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)
