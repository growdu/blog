# postgresql源码阅读（一）

```shell
src/backend/main/main.c
```

```c
    progname = get_progname(argv[0]);

	/*
	 * Platform-specific startup hacks
	 */
	startup_hacks(progname);

	/*
	 * Remember the physical location of the initially given argv[] array for
	 * possible use by ps display.  On some platforms, the argv[] storage must
	 * be overwritten in order to set the process title for ps. In such cases
	 * save_ps_display_args makes and returns a new copy of the argv[] array.
	 *
	 * save_ps_display_args may also move the environment strings to make
	 * extra room. Therefore this should be done as early as possible during
	 * startup, to avoid entanglements with code that might save a getenv()
	 * result pointer.
	 */
	argv = save_ps_display_args(argc, argv);
```

这个代码片段的主要目的是在程序启动时进行一些特定平台的初始化，并保存原始的 `argv[]` 数组以便在设置进程标题时使用。以下是详细解析：

### 1. 获取程序名称
```c
progname = get_progname(argv[0]);
```
这行代码调用 `get_progname` 函数并传入程序的第一个命令行参数（通常是程序自身的路径）。`get_progname` 函数返回处理后的程序名称并赋值给 `progname` 变量。

### 2. 执行平台特定的启动黑客

```c
/*
 * Platform-specific startup hacks
 */
startup_hacks(progname);
```
这里调用 `startup_hacks` 函数并传入程序名称 `progname`。这个函数执行一些特定平台的初始化操作，这些操作可能包括设置环境变量、调整系统配置等。

### 3. 记住最初的 `argv[]` 数组的物理位置

```c
/*
 * Remember the physical location of the initially given argv[] array for
 * possible use by ps display.  On some platforms, the argv[] storage must
 * be overwritten in order to set the process title for ps. In such cases
 * save_ps_display_args makes and returns a new copy of the argv[] array.
 *
 * save_ps_display_args may also move the environment strings to make
 * extra room. Therefore this should be done as early as possible during
 * startup, to avoid entanglements with code that might save a getenv()
 * result pointer.
 */
argv = save_ps_display_args(argc, argv);
```
这部分代码涉及保存最初的 `argv[]` 数组的位置，以便可能在进程显示（例如 `ps` 命令）中使用。在某些平台上，为了设置进程标题，可能需要覆盖 `argv[]` 的存储。在这种情况下，`save_ps_display_args` 函数会创建并返回 `argv[]` 数组的新副本。

- `save_ps_display_args` 函数还可能移动环境字符串以腾出额外的空间。因此，这个操作应尽早进行，以避免与可能保存 `getenv()` 结果指针的代码发生冲突。

### 总结
这个代码片段在程序启动时进行了一些重要的初始化操作：

1. 获取并处理程序名称。
2. 执行特定平台的初始化操作。
3. 保存最初的 `argv[]` 数组的位置，以便在某些平台上设置进程标题时使用。这个操作尽早进行，以避免与其他代码发生冲突。

## postgresql为什么需要执行save_ps_display_args

PostgreSQL 执行 `save_ps_display_args` 的原因主要与进程状态显示有关。以下是详细解析：

### 1. 进程状态显示的重要性
在许多操作系统中，工具如 `ps`、`top` 等可以显示当前系统中正在运行的进程及其状态。这些工具通常会显示进程的命令行参数，以帮助管理员了解每个进程的用途和状态。对于数据库服务器（如 PostgreSQL）来说，能够显示详细的进程状态信息是非常重要的，因为这有助于监控和调试数据库活动。

### 2. 覆盖 `argv[]` 的原因
在一些平台上，要更改进程的状态显示，需要覆盖 `argv[]` 数组中的内容。这是因为 `argv[]` 数组通常存储在进程的内存空间中，而操作系统使用这些信息来显示进程的命令行参数。

### 3. `save_ps_display_args` 的作用
`save_ps_display_args` 函数的主要作用是目的是保存原始的命令行参数 (argv[]) 和环境变量 (environ[]) 的位置，并在需要时将它们复制到新的内存区域中，以便能够安全地修改原始 argv[] 和 environ[] 的内容来显示自定义的进程状态。这个新的副本可以用于覆盖 `argv[]`，以便更改进程的状态显示。具体来说，`save_ps_display_args` 执行以下操作：

1. **保存初始状态：** 将原始的 `argv[]` 数组内容保存起来，以便在需要时可以恢复。
2. **创建副本：** 在某些平台上（如 Linux），需要通过修改 `argv[]` 来更新进程状态显示。`save_ps_display_args` 会创建一个新的 `argv[]` 副本，用于存储这些修改。
3. **移动环境变量：** 为了腾出额外的空间，`save_ps_display_args` 可能会移动环境变量字符串。这有助于确保有足够的空间来存储新的进程状态信息。

### 4. 早期执行的必要性
由于 `save_ps_display_args` 可能会移动环境变量字符串，因此需要尽早执行此操作，以避免与其他可能保存 `getenv()` 结果指针的代码发生冲突。如果其他代码在 `save_ps_display_args` 执行之后试图访问环境变量，可能会导致不一致或错误。

### 总结
PostgreSQL 执行 `save_ps_display_args` 的主要原因是为了能够动态更新进程的状态显示信息。通过保存和覆盖 `argv[]` 数组，PostgreSQL 可以在运行时提供详细的进程状态信息，这对于数据库的监控和调试非常重要。尽早执行 `save_ps_display_args` 可以避免潜在的冲突，确保环境变量的正确性。

## postgresql源码中MemoryContextInit做了什么事情

在 PostgreSQL 的源码中，`MemoryContextInit` 函数负责初始化内存上下文管理系统，这是 PostgreSQL 内存分配和管理机制的核心部分。以下是详细解析：

### 1. 内存上下文的概念
内存上下文（`MemoryContext`）是 PostgreSQL 中用于管理内存分配的抽象层。它允许程序以分层方式管理内存，从而可以方便地在某些情况下释放大量内存（如在事务结束时）。每个内存上下文都是一个独立的内存区域，具有自己的分配策略和生命周期。

### 2. `MemoryContextInit` 的目的
`MemoryContextInit` 函数的主要目的是初始化内存上下文系统，确保在程序运行期间可以有效地管理内存。这个函数通常在 PostgreSQL 启动时调用。

### 3. `MemoryContextInit` 的实现
让我们看一下 `MemoryContextInit` 的实现，以了解其具体做了哪些事情：

```c
void
MemoryContextInit(void)
{
    /* Initialize TopMemoryContext as an AllocSetContext */
    TopMemoryContext = AllocSetContextCreate(NULL,
                                             "TopMemoryContext",
                                             ALLOCSET_DEFAULT_SIZES);

    /* Initialize CurrentMemoryContext to point to TopMemoryContext */
    CurrentMemoryContext = TopMemoryContext;

    /* Initialize ErrorContext, which will be used for error reporting */
    ErrorContext = AllocSetContextCreate(TopMemoryContext,
                                         "ErrorContext",
                                         ALLOCSET_DEFAULT_SIZES);

    /* Initialize other special contexts, if any */
    /* e.g., CacheMemoryContext, MessageContext, etc. */
}
```

### 4. 解析每个步骤

#### a. 初始化 `TopMemoryContext`
```c
TopMemoryContext = AllocSetContextCreate(NULL, "TopMemoryContext", ALLOCSET_DEFAULT_SIZES);
```
这行代码创建了一个顶级内存上下文 `TopMemoryContext`，使用 `AllocSetContextCreate` 函数分配内存并初始化它。`TopMemoryContext` 是所有其他内存上下文的根，其他上下文都是它的子上下文。

#### b. 设置 `CurrentMemoryContext`
```c
CurrentMemoryContext = TopMemoryContext;
```
将当前内存上下文设置为 `TopMemoryContext`。`CurrentMemoryContext` 是一个全局变量，指向当前正在使用的内存上下文。

#### c. 初始化 `ErrorContext`
```c
ErrorContext = AllocSetContextCreate(TopMemoryContext, "ErrorContext", ALLOCSET_DEFAULT_SIZES);
```
创建并初始化 `ErrorContext`，用于错误报告和处理。`ErrorContext` 是在错误发生时分配内存的地方，以确保在内存不足或其他严重错误情况下仍能分配内存进行错误报告。

#### d. 初始化其他特殊上下文
```c
/* Initialize other special contexts, if any */
/* e.g., CacheMemoryContext, MessageContext, etc. */
```
如果有其他特殊的内存上下文（如缓存上下文 `CacheMemoryContext`、消息上下文 `MessageContext` 等），则在这里进行初始化。

### 5. 总结
`MemoryContextInit` 函数初始化了 PostgreSQL 内存管理系统的核心部分，通过设置顶级内存上下文和一些特殊的内存上下文，为整个系统的内存分配和管理奠定了基础。这些内存上下文提供了一种结构化的方式来管理内存，使得内存的分配和释放更加高效和可靠。

## set_pglocale_pgservice(argv[0], PG_TEXTDOMAIN("postgres"));做了什么事

在 PostgreSQL 的源码中，`set_pglocale_pgservice` 函数用于设置本地化和服务配置。具体来说，这一调用：
```c
set_pglocale_pgservice(argv[0], PG_TEXTDOMAIN("postgres"));
```
主要有两个目的：

1. **设置本地化（locale）信息**，包括语言环境和消息域（text domain）。
2. **配置 PostgreSQL 服务相关的信息**。

让我们逐步解析这两个部分。

### 1. `PG_TEXTDOMAIN("postgres")` 的作用
`PG_TEXTDOMAIN` 宏用于定义消息域，这里传递了 `"postgres"` 作为消息域。消息域用于标识特定应用程序的消息字符串，可以帮助定位和加载正确的翻译文件。

### 2. `set_pglocale_pgservice` 函数的作用
`set_pglocale_pgservice` 函数的定义位于 `src/common/exec.c` 文件中。该函数主要执行以下操作：

- 初始化本地化信息。
- 设置应用程序的服务配置。

以下是 `set_pglocale_pgservice` 函数的大致实现：

```c
void
set_pglocale_pgservice(const char *argv0, const char *app)
{
    set_pglocale(argv0, app);
    set_pgservice(argv0, app);
}
```

可以看到，`set_pglocale_pgservice` 调用了两个函数：`set_pglocale` 和 `set_pgservice`。

#### a. `set_pglocale` 函数
`set_pglocale` 函数用于初始化本地化设置，通常会设置语言环境和消息域。具体实现如下：

```c
void
set_pglocale(const char *argv0, const char *app)
{
    char    path[MAXPGPATH];

    /* set the text domain for translations */
    bindtextdomain(app, LOCALEDIR);

    /* also make the message catalog available for error messages */
    bind_textdomain_codeset(app, "UTF-8");

    /* Compute the real application path */
    if (find_my_exec(argv0, path) < 0)
        return;

    /* Set the application locale directory */
    setlocale(LC_MESSAGES, "");
    setlocale(LC_CTYPE, "");
}
```

- `bindtextdomain(app, LOCALEDIR)`: 绑定消息域 `app` 到本地化目录 `LOCALEDIR`。
- `bind_textdomain_codeset(app, "UTF-8")`: 设置消息域 `app` 使用 UTF-8 字符集。
- `setlocale(LC_MESSAGES, "")`: 设置消息的本地化。
- `setlocale(LC_CTYPE, "")`: 设置字符类型的本地化。

#### b. `set_pgservice` 函数
`set_pgservice` 函数用于初始化与 PostgreSQL 服务相关的设置：

```c
void
set_pgservice(const char *argv0, const char *app)
{
    char    path[MAXPGPATH];

    /* Compute the real application path */
    if (find_my_exec(argv0, path) < 0)
        return;

    /* Do something related to service configuration */
    ...
}
```

这里 `find_my_exec(argv0, path)` 用于计算程序的真实路径。具体的服务配置细节可能包括设置环境变量或者其他与 PostgreSQL 服务相关的配置。

### 总结
调用 `set_pglocale_pgservice(argv[0], PG_TEXTDOMAIN("postgres"))` 的主要作用是：
- 通过 `set_pglocale` 初始化本地化设置，绑定消息域并设置字符集。
- 通过 `set_pgservice` 进行与 PostgreSQL 服务相关的初始化配置。

这些设置确保了 PostgreSQL 能够正确处理本地化消息，并配置其运行环境以提供所需的服务。

## 在linux中，本地化消息有什么用

在 Linux 中，本地化消息（localized messages）对于提供多语言支持和改善用户体验具有重要作用。具体来说，本地化消息可以：

### 1. 提供多语言支持
本地化消息使得软件能够根据用户的语言偏好显示信息。例如，软件可以根据用户的语言环境（locale）显示错误消息、提示和菜单选项。这对于非英语母语的用户尤为重要，使他们能够更轻松地使用软件。

### 2. 改善用户体验
通过使用用户的母语或偏好语言，软件可以提供更友好和直观的界面。用户更容易理解和操作软件，从而提高效率和满意度。

### 3. 增加软件的市场接受度
支持多语言的应用程序能够覆盖更广泛的用户群体，包括不同国家和地区的用户。这对于开源项目和商业软件都是至关重要的，可以提高软件的全球接受度和使用率。

### 4. 遵循国际化标准
使用本地化消息有助于遵循国际化（i18n）和本地化（l10n）标准。这些标准规定了如何设计和开发软件以便于在不同语言和地区之间进行切换，从而减少在不同市场中进行定制化工作的成本和复杂性。

### 5. 简化开发和维护
通过使用本地化消息，开发者可以将文本内容与代码逻辑分离。这使得翻译工作可以独立进行，而不需要修改代码逻辑，从而简化了开发和维护工作。例如，GNU `gettext` 工具集就是一个常用的本地化框架，它提供了提取、翻译和应用本地化字符串的工具。

### 6. 增强可访问性
对于有视力障碍或其他阅读障碍的用户，软件可以通过本地化消息提供更好的支持。例如，通过使用适当的本地化和屏幕阅读器兼容的消息，软件可以为这些用户提供更好的体验。

### 实际示例
在 Linux 系统中，本地化消息通常通过设置环境变量来实现，例如 `LANG`、`LC_MESSAGES` 和 `LC_ALL`。这些变量控制了应用程序的语言环境。以下是一个示例：

```bash
export LANG=zh_CN.UTF-8
```

这行命令设置系统的语言环境为简体中文（UTF-8 编码），之后运行的应用程序如果支持简体中文，就会显示简体中文的消息。

### 总结
在 Linux 中，本地化消息极大地提高了软件的可用性、用户体验和市场接受度。通过支持多语言和遵循国际化标准，开发者可以创建更具包容性的应用程序，满足全球用户的需求。

```c
/*
	 * In the postmaster, absorb the environment values for LC_COLLATE and
	 * LC_CTYPE.  Individual backends will change these later to settings
	 * taken from pg_database, but the postmaster cannot do that.  If we leave
	 * these set to "C" then message localization might not work well in the
	 * postmaster.
	 */
	init_locale("LC_COLLATE", LC_COLLATE, "");
	init_locale("LC_CTYPE", LC_CTYPE, "");

	/*
	 * LC_MESSAGES will get set later during GUC option processing, but we set
	 * it here to allow startup error messages to be localized.
	 */
#ifdef LC_MESSAGES
	init_locale("LC_MESSAGES", LC_MESSAGES, "");
#endif

	/*
	 * We keep these set to "C" always, except transiently in pg_locale.c; see
	 * that file for explanations.
	 */
	init_locale("LC_MONETARY", LC_MONETARY, "C");
	init_locale("LC_NUMERIC", LC_NUMERIC, "C");
	init_locale("LC_TIME", LC_TIME, "C");

	/*
	 * Now that we have absorbed as much as we wish to from the locale
	 * environment, remove any LC_ALL setting, so that the environment
	 * variables installed by pg_perm_setlocale have force.
	 */
	unsetenv("LC_ALL");
```

在 PostgreSQL 的源码中，上述代码片段主要处理了服务器启动时的本地化（locale）设置。具体来说，这段代码初始化了与语言环境相关的设置，以确保在服务器启动过程中和运行期间能够正确处理本地化消息和数据格式。以下是对每个部分的详细解析：

### 1. 吸收环境变量值

#### LC_COLLATE 和 LC_CTYPE
```c
/*
 * In the postmaster, absorb the environment values for LC_COLLATE and
 * LC_CTYPE.  Individual backends will change these later to settings
 * taken from pg_database, but the postmaster cannot do that.  If we leave
 * these set to "C" then message localization might not work well in the
 * postmaster.
 */
init_locale("LC_COLLATE", LC_COLLATE, "");
init_locale("LC_CTYPE", LC_CTYPE, "");
```

- **LC_COLLATE**: 用于字符串比较和排序。
- **LC_CTYPE**: 用于字符分类和转换。

在 `postmaster` 进程中，吸收环境变量的值来设置 `LC_COLLATE` 和 `LC_CTYPE`。虽然每个后端进程会根据数据库的设置（从 `pg_database` 中获取）来改变这些值，但 `postmaster` 进程无法这样做。如果保持为 "C"，则消息本地化可能无法正常工作。

### 2. 设置 LC_MESSAGES
```c
/*
 * LC_MESSAGES will get set later during GUC option processing, but we set
 * it here to allow startup error messages to be localized.
 */
#ifdef LC_MESSAGES
init_locale("LC_MESSAGES", LC_MESSAGES, "");
#endif
```

- **LC_MESSAGES**: 用于确定消息的语言环境。

尽管 `LC_MESSAGES` 会在后续的 GUC（Grand Unified Configuration）选项处理过程中设置，但这里提前设置是为了在启动过程中本地化错误消息。

### 3. 将其他语言环境变量设置为 "C"
```c
/*
 * We keep these set to "C" always, except transiently in pg_locale.c; see
 * that file for explanations.
 */
init_locale("LC_MONETARY", LC_MONETARY, "C");
init_locale("LC_NUMERIC", LC_NUMERIC, "C");
init_locale("LC_TIME", LC_TIME, "C");
```

- **LC_MONETARY**: 用于货币格式。
- **LC_NUMERIC**: 用于数字格式。
- **LC_TIME**: 用于时间和日期格式。

这些设置始终保持为 "C"，除非在 `pg_locale.c` 文件中临时改变。这样做是为了避免在处理货币、数字和时间格式时出现不一致的问题。

### 4. 移除 LC_ALL 设置
```c
/*
 * Now that we have absorbed as much as we wish to from the locale
 * environment, remove any LC_ALL setting, so that the environment
 * variables installed by pg_perm_setlocale have force.
 */
unsetenv("LC_ALL");
```

移除环境变量 `LC_ALL` 的设置。`LC_ALL` 是一个高优先级的环境变量，如果设置了它，会覆盖其他 `LC_*` 环境变量。移除 `LC_ALL` 可以确保我们之前通过 `init_locale` 设置的 `LC_*` 环境变量生效。

### 总结
这段代码确保了在 PostgreSQL 服务器启动时正确初始化语言环境设置，使得消息本地化和数据格式处理能够按照预期工作。通过吸收环境变量值并设置关键的 `LC_*` 环境变量，它为 PostgreSQL 提供了灵活的本地化支持，确保服务器在不同语言和区域设置下能够正常运行。