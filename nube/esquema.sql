-- ============================================================================
--  Libro de Fiados - base de datos compartida (Supabase / PostgreSQL)
--
--  Esto es lo que ven el computador del local y el celular. Se pega entero en
--  Supabase: menu "SQL Editor" -> "New query" -> pegar -> "Run".
--  Se puede correr de nuevo sin miedo: no borra nada de lo que ya exista.
--
--  Ideas detras del diseno:
--   - Cada fila tiene un codigo unico (uuid). Asi el computador y el celular
--     pueden anotar al mismo tiempo sin pisarse.
--   - Nada se borra de verdad: se marca "borrado". Si no, un dispositivo que
--     estuvo sin internet reviviria lo que el otro borro.
--   - Cada fila guarda "actualizado" (lo pone el servidor, no el dispositivo,
--     asi no importa si un reloj esta corrido). Sincronizar es preguntar:
--     "dame todo lo que cambio despues de esta hora".
--   - Todo cuelga de un "local". Hoy hay uno solo (El Buen Corte), pero el dia
--     que se le venda a otra carniceria, no hay nada que rehacer.
-- ============================================================================

-- ---------------------------------------------------------------- los locales
create table if not exists public.locales (
    id      uuid primary key default gen_random_uuid(),
    nombre  text not null,
    ciudad  text not null default '',
    creado  timestamptz not null default now()
);

-- Quien puede entrar a cada local. Una fila por persona (el dueno, y manana
-- quien atienda el mostrador).
create table if not exists public.miembros (
    user_id  uuid not null references auth.users(id) on delete cascade,
    local_id uuid not null references public.locales(id) on delete cascade,
    rol      text not null default 'dueno',
    creado   timestamptz not null default now(),
    primary key (user_id, local_id)
);

-- ---------------------------------------------------------------- el libro
create table if not exists public.clientes (
    id          uuid primary key,
    local_id    uuid not null references public.locales(id) on delete cascade,
    nombre      text not null,
    telefono    text not null default '',
    nota        text not null default '',
    activo      boolean not null default true,     -- false = archivado
    borrado     boolean not null default false,
    creado      timestamptz not null default now(),
    actualizado timestamptz not null default now()
);

-- Lo que se anoto: que se llevo y cuanto vale.
create table if not exists public.compras (
    id          uuid primary key,
    local_id    uuid not null references public.locales(id) on delete cascade,
    cliente_id  uuid not null references public.clientes(id) on delete cascade,
    fecha       date not null,
    detalle     text not null default '',
    monto       integer not null check (monto > 0),   -- pesos, sin decimales
    borrado     boolean not null default false,
    creado      timestamptz not null default now(),
    actualizado timestamptz not null default now()
);

-- La plata que entrego el cliente (un abono o el pago completo).
create table if not exists public.pagos (
    id          uuid primary key,
    local_id    uuid not null references public.locales(id) on delete cascade,
    cliente_id  uuid not null references public.clientes(id) on delete cascade,
    fecha       date not null,
    monto       integer not null check (monto > 0),
    nota        text not null default '',
    borrado     boolean not null default false,
    creado      timestamptz not null default now(),
    actualizado timestamptz not null default now()
);

-- Cuanto de cada pago fue a cada compra. Es lo que permite decir, de cada
-- compra, si esta pendiente, a medias o pagada.
create table if not exists public.aplicaciones (
    id          uuid primary key,
    local_id    uuid not null references public.locales(id) on delete cascade,
    pago_id     uuid not null references public.pagos(id) on delete cascade,
    compra_id   uuid not null references public.compras(id) on delete cascade,
    monto       integer not null check (monto > 0),
    borrado     boolean not null default false,
    creado      timestamptz not null default now(),
    actualizado timestamptz not null default now()
);

-- --------------------------------------------------- "dame lo que cambio"
-- Sincronizar es leer por (local_id, actualizado), asi que ese es el indice.
create index if not exists ix_clientes_sync     on public.clientes     (local_id, actualizado);
create index if not exists ix_compras_sync      on public.compras      (local_id, actualizado);
create index if not exists ix_pagos_sync        on public.pagos        (local_id, actualizado);
create index if not exists ix_aplicaciones_sync on public.aplicaciones (local_id, actualizado);
create index if not exists ix_compras_cliente   on public.compras      (cliente_id);
create index if not exists ix_pagos_cliente     on public.pagos        (cliente_id);
create index if not exists ix_apl_compra        on public.aplicaciones (compra_id);
create index if not exists ix_apl_pago          on public.aplicaciones (pago_id);

-- La hora del ultimo cambio la pone el servidor, siempre.
create or replace function public.marcar_actualizado()
returns trigger language plpgsql as $$
begin
    new.actualizado := now();
    if tg_op = 'UPDATE' then
        new.creado := old.creado;        -- la fecha de nacimiento no se cambia
    end if;
    return new;
end $$;

do $$
declare t text;
begin
    foreach t in array array['clientes', 'compras', 'pagos', 'aplicaciones'] loop
        execute format('drop trigger if exists t_actualizado on public.%I', t);
        execute format('create trigger t_actualizado before insert or update on public.%I
                        for each row execute function public.marcar_actualizado()', t);
    end loop;
end $$;

-- ------------------------------------------------------------- las llaves
-- Cada quien ve solo los locales a los que pertenece.
create or replace function public.mis_locales()
returns setof uuid language sql stable security definer set search_path = public as $$
    select local_id from public.miembros where user_id = auth.uid()
$$;

alter table public.locales      enable row level security;
alter table public.miembros     enable row level security;
alter table public.clientes     enable row level security;
alter table public.compras      enable row level security;
alter table public.pagos        enable row level security;
alter table public.aplicaciones enable row level security;

drop policy if exists p_locales  on public.locales;
create policy p_locales on public.locales for select
    using (id in (select public.mis_locales()));

drop policy if exists p_miembros on public.miembros;
create policy p_miembros on public.miembros for select
    using (user_id = auth.uid());

do $$
declare t text;
begin
    foreach t in array array['clientes', 'compras', 'pagos', 'aplicaciones'] loop
        execute format('drop policy if exists p_%1$s on public.%1$I', t);
        execute format('create policy p_%1$s on public.%1$I for all
                          using (local_id in (select public.mis_locales()))
                          with check (local_id in (select public.mis_locales()))', t);
    end loop;
end $$;

-- ================================================================= usuarios
--  El dueno puede dar y quitar acceso a otras personas (por ejemplo quien
--  atiende el mostrador) desde el mismo programa, sin entrar aqui.
--
--  Estas funciones corren "en nombre del sistema" (security definer), asi que
--  cada una parte comprobando quien la llama: si no es el dueno del local, no
--  hace nada. Es la unica forma de que el programa instalado en el local no
--  necesite llevar adentro ninguna llave secreta.
-- ==========================================================================

-- Quienes pueden entrar a mi local.
create or replace function public.usuarios_del_local()
returns table (correo text, rol text, desde timestamptz)
language sql stable security definer set search_path = public as $$
    select u.email::text, m.rol, m.creado
      from public.miembros m
      join auth.users u on u.id = m.user_id
     where m.local_id in (select public.mis_locales())
     order by (m.rol = 'dueno') desc, m.creado
$$;

-- Darle acceso a alguien que ya tiene cuenta creada.
create or replace function public.agregar_al_local(p_correo text,
                                                   p_rol text default 'ayudante')
returns text language plpgsql security definer set search_path = public as $$
declare
    v_local uuid;
    v_user  uuid;
begin
    select local_id into v_local
      from public.miembros
     where user_id = auth.uid() and rol = 'dueno'
     limit 1;
    if v_local is null then
        raise exception 'Solo el dueño puede dar acceso a otras personas.';
    end if;

    select id into v_user from auth.users
     where lower(email) = lower(trim(p_correo));
    if v_user is null then
        raise exception 'Todavía no hay una cuenta con el correo %. Créala primero.',
                        p_correo;
    end if;

    insert into public.miembros (user_id, local_id, rol)
    values (v_user, v_local, coalesce(nullif(trim(p_rol), ''), 'ayudante'))
    on conflict (user_id, local_id) do update set rol = excluded.rol;
    return 'listo';
end $$;

-- Quitarle el acceso a alguien (la cuenta sigue existiendo, pero ya no ve el local).
create or replace function public.quitar_del_local(p_correo text)
returns text language plpgsql security definer set search_path = public as $$
declare
    v_local uuid;
    v_user  uuid;
begin
    select local_id into v_local
      from public.miembros
     where user_id = auth.uid() and rol = 'dueno'
     limit 1;
    if v_local is null then
        raise exception 'Solo el dueño puede quitar el acceso.';
    end if;

    select id into v_user from auth.users where lower(email) = lower(trim(p_correo));
    if v_user is null then
        raise exception 'No hay ninguna cuenta con el correo %.', p_correo;
    end if;
    if v_user = auth.uid() then
        raise exception 'El dueño no se puede quitar a sí mismo.';
    end if;

    delete from public.miembros where user_id = v_user and local_id = v_local;
    return 'listo';
end $$;

revoke execute on function public.usuarios_del_local()          from anon;
revoke execute on function public.agregar_al_local(text, text)  from anon;
revoke execute on function public.quitar_del_local(text)        from anon;
grant  execute on function public.usuarios_del_local()          to authenticated;
grant  execute on function public.agregar_al_local(text, text)  to authenticated;
grant  execute on function public.quitar_del_local(text)        to authenticated;

-- ============================================================================
--  LISTO. Ahora falta crear el local y decir quien entra: eso va en el
--  archivo "primer-uso.sql", despues de crear el usuario del dueno.
-- ============================================================================
