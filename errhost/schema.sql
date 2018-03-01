drop table if exists sessions;
create table sessions (
    sessionid integer primary key autoincrement,
    username text not null,
    filename text not null,
    createdon text not null,
    filesize integer not null
);
drop table if exists errors;
create table errors (
    errid integer primary key autoincrement,
    lineno integer not null,
    errtype text not null,
    errmsg text not null,
    numofdups integer not null,
    sessionid integer,
    foreign key(sessionid) references sessions(sessionid)
);
drop table if exists uniq_errors;
create table uniq_errors (
    id integer primary key autoincrement,
    errtype text not null,
    errmsg text not null,
    sessionid integer not null,
    rating integer default 0,
    repeated integer default 1
);
