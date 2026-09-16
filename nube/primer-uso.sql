-- ============================================================================
--  Segundo paso: crear el local y decir quien puede entrar.
--
--  ANTES de correr esto hay que haber creado el usuario del dueno en Supabase:
--  menu "Authentication" -> "Users" -> "Add user" -> "Create new user",
--  con su correo y una clave, marcando "Auto Confirm User".
--
--  Despues: cambiar el correo de la linea marcada por el de verdad, pegar todo
--  en el SQL Editor y apretar "Run". Se puede correr dos veces sin romper nada.
-- ============================================================================

do $$
declare
    -- >>>>>>>>>>>>  CAMBIAR ESTE CORREO POR EL DEL DUENO  <<<<<<<<<<<<
    v_correo text := 'correo-del-dueno@ejemplo.cl';

    v_local   uuid;
    v_usuario uuid;
begin
    -- El local (si ya existe, se reutiliza).
    select id into v_local from public.locales
     where nombre = 'Carnicería El Buen Corte';
    if v_local is null then
        insert into public.locales (nombre, ciudad)
        values ('Carnicería El Buen Corte', 'Loncoche')
        returning id into v_local;
    end if;

    -- El usuario que se creo en Authentication.
    select id into v_usuario from auth.users where lower(email) = lower(v_correo);
    if v_usuario is null then
        raise exception
            'No hay ningun usuario con el correo "%". Crealo primero en el menu '
            'Authentication -> Users -> Add user, y despues corre esto de nuevo.',
            v_correo;
    end if;

    -- Queda como dueno del local.
    insert into public.miembros (user_id, local_id, rol)
    values (v_usuario, v_local, 'dueno')
    on conflict (user_id, local_id) do nothing;

    raise notice 'Listo: % entra al local %', v_correo, v_local;
end $$;

-- Esto es lo que hay que copiar y mandarle a Macoem:
select l.id   as local_id,
       l.nombre,
       u.email as entra_con
  from public.locales l
  join public.miembros m on m.local_id = l.id
  join auth.users u      on u.id = m.user_id
 where l.nombre = 'Carnicería El Buen Corte';
