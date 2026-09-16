-- ============================================================================
--  Segundo paso: crear el local y decir quien puede entrar.
--
--  ANTES de correr esto hay que haber creado el usuario del dueno en Supabase:
--  menu "Authentication" -> "Users" -> "Add user" -> "Create new user",
--  con su correo y una clave.
--
--  Despues: cambiar el correo de abajo por el de verdad y correr todo en el
--  SQL Editor. Se puede correr dos veces sin romper nada.
-- ============================================================================

-- >>> CAMBIAR ESTE CORREO POR EL DEL USUARIO QUE SE CREO <<<
\set correo 'correo-del-dueno@ejemplo.cl'

-- El local (si ya existe, no se duplica).
insert into public.locales (nombre, ciudad)
select 'Carnicería El Buen Corte', 'Loncoche'
where not exists (select 1 from public.locales where nombre = 'Carnicería El Buen Corte');

-- El dueno queda como miembro del local.
insert into public.miembros (user_id, local_id, rol)
select u.id, l.id, 'dueno'
  from auth.users u, public.locales l
 where u.email = :'correo'
   and l.nombre = 'Carnicería El Buen Corte'
on conflict (user_id, local_id) do nothing;

-- Para copiar: este es el codigo del local que necesita la aplicacion.
select l.id as local_id, l.nombre, u.email as entra_con
  from public.locales l
  join public.miembros m on m.local_id = l.id
  join auth.users u on u.id = m.user_id
 where l.nombre = 'Carnicería El Buen Corte';
