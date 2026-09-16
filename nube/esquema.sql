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

-- ============================================================================
--  LISTO. Ahora falta crear el local y decir quien entra: eso va en el
--  archivo "primer-uso.sql", despues de crear el usuario del dueno.
-- ============================================================================
