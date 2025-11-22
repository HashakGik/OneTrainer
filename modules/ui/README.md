QT6 GUI Overview
=================



## Overall Architecture

The GUI has been completely re-implemented as a Model-View-Controller architecture, for better future-proofing.
The folder structure is the following:
- `modules/ui/models`: OneTrainer functionalities, abstracted from GUI implementation
- `modules/ui/controllers`: Linker classes, managing how models should be invoked, validating (complex) user inputs and orchestrating GUI behavior
- `modules/ui/views`: `*.ui` files drawing each component, in a way which is as data-agnostic as possible
- `modules/ui/utils`: auxiliary classes.

### Models
Model classes collect original OneTrainer functionalities, abstracting from the specific user interface.
As models can potentially be invoked from different processes/threads/event loops, each operation modifying internal states must be thread-safe.

Models subclassing `SingletonConfigModel` wrap `modules.util.config` classes, exposing a singleton interface and a thread-safe dot-notation-based read/write mechanism.

Other models provide auxiliary utilities (e.g., open the browser, load files, etc.) and are mostly grouped conceptually (i.e., all file operations are handled by the same class).

Thread-safe access to model objects is mediated by a global QSimpleMutex, shared by every subclass of `SingletonConfigModel`. Multiple levels of synchronization are possible:
- Each model has a `self.config` attribute which can be accessed safely with `Whatever.instance().getState(var)` and `Whatever.instance().setState(var, value)` (or unsafely with `Whatever.instance().config.var`)
- The `with self.critical_region()` context manager allows to wrap a block of code that may become inconsistent if interrupted (e.g., computing something based on two variables)
- The `SingletonConfigModel.atomic` decorator wraps an entire method to prevent inconsistencies. Note that this does not mean that every other thread is frozen, only that access to model variables is delayed until the method exits.
- The `with self.freeze_state()` context manager creates a read-only frozen copy, from which `self.getState()` will transparently read. This is useful for situations in which there are multiple variables to read, and the user may change UI elements while a function is operating in the background.


Although most of the processing in OneTrainer is handled by a single thread, it is good practice to block shared resources for the least amount necessary (i.e., avoid wrapping everything with `@SingletonConfigModel.atomic`, which would negate any performance improvement of an event-based GUI engine such as QT6).
For now, I am using only `getState/setState` in a naive way, and `@SingletonConfigModel.atomic` for small methods. This is just for ease of debugging in this phase. I expect this approach to cause unwanted behavior when the user starts a lengthy operation (e.g., captioning files), and changes some values before processing has finished (the use case for which `freeze_state()` was intended).
In the future, a principled approach would be to freeze the state for read-only functions, and use critical regions for blocks of write accesses.

Note: `freeze_state` is currently untested, and probably will set as read-only *EVERY* subclass of `SingletonConfigModel`, rather than just `self`.


### Controllers
Controller classes are finite-state machines that initialize themselves with a specific sequence of events, and then react to external events (slots/signals).
Each controller is associated with a view (`self.ui`) and is optionally associated with a parent controller (`self.parent`), creating a hierarchy with the `OneTrainerController` at the root.

At construction, each controller executes these operations:
1. `BaseController.__init__`: initializes the view
2. `_setup()`: setups additional attributes (e.g., references to model classes)
3. `_connectUIBehavior()`: forms static connections between signals and slots (e.g., button behaviors)
4. `_connectInputValidation()`: associates complex validation functions (QValidators, slots, or other mechanisms) to each control (simple validations are defined in view files)
5. `_loadPresets()`: for controls that contain variable data (e.g., QComboBox), loads the list of values (typically from a `modules.util.enum` class, or from files)
6. Connect static controls according to `self.state_ui_connections` dict: connects ui elements to `StateModel` variables bidirectionally (every time a control is changed, the `TrainConfig` is updated, and every time `stateChanged` is emitted, the control is updated)
7. `self.__init__`: Additional controller-specific initializations (usually connections of dynamic controls)

The `state_ui_connections` dictionary contains pairs `{'train_config_variable': 'ui_element'}` for ease of connection, and a similar pattern is often used for other connections.
Every interaction with non-GUI code (e.g., progress bar updates, training, etc.) is mediated by signals/slots which invoke model methods.

Controllers also have the responsibility of owning and handling additional threads. This is to guarantee better encapsulation and future-proofing, as changing libraries or invocation patterns will allow to keep the models untouched.

Violations of the Model-View-Controller architecture:
- Temporarily, optimizer default values are copied in the `modules.ui.controllers.windows.optimizer` controller.

### Views
View files are created with QtCreator, or QtDesigner, and assumed to expose, whenever possible,data-agnostic controls (e.g., a QComboBox for data types, the values of which are populated at runtime).

Naming convention: each widget within a `*.ui` file is either a decoration (e.g., a static label or a spacer) with its default name (e.g. `label_42`), or is associated with a meaningful name in the form `camelCaseControlNameXxx`,
where `Xxx` is a class identifier:
- `Lbl`: QLabel
- `Led`: QLineEdit
- `Ted`: QTextEdit
- `Cbx`: QComboBox
- `Sbx`: QSpinBox or QDoubleSpinBox
- `Cmb`: QComboBox
- `Lay`: QVerticalLayout, QHorizontalLayout or QGridLayout
- `Btn`: QPushButton or QToolButton.

This convention has no real use, other than allowing contributors to quickly tell from the name which signals/slots are supported by a given UI element.

Suggested development checklist:
1. Create UI layout
2. Assign widget attributes (name, text, size policy, tooltip, etc.)
3. Assign buddies for labels
4. Edit tab order
5. Connect trivial (same signature, no processing) signals and slots
6. Assign simple validations (e.g., QSpinBox min/max values, QLineEdit masks, etc.)

Violations of the Model-View-Controller architecture:
- The fields of the optimizer window are created dynamically from its controller. This was mostly to avoid having a hard to maintain `.ui` file.

### Utils
Auxiliary, but QT-dependent, classes.

- `FigureWidget`: Figure widget for plots and images. Can be instantiated with a toolbar for inspection or image editing (arbitrary tools are managed by the controller instantiating the widget).
- `OneTrainerApplication`: Subclass of QApplication defining global signals
- `SNLineEdit`: Scientific notation Line Edit Widget
- `WorkerPool`: Generic threaded processor executing functions on a thread pool automatically managed. Functions can be made reentrant (i.e., they will be executed once, even when multiple calls are made, useful for example when a user attempts to scan the same folder before the previous operation terminated) if they are associated with a name.

## QT6 Notions
The following are some basic notions for useful QT6 features.

Signal-slot connections: QT's interactions are asynchronous and based on message passing. Each widget exposes two types of methods:
- Signals are fired when a particular event occurs (e.g., a QPushButton is clicked) or when explicitly `emit()`ed. Some signals are associated with data (e.g., `QLineEdit.textChanged` also transmits the text in a string parameter).
- Slots are functions receiving a signal and processing its data. For efficiency reasons, they should be annotated with a `@Slot(types)` decorator, but arbitrary python functions can act as slots, as long as their parameters match the signal.
- The `@Slot` decorator does not accept the idiom `type|None`, you can either use "normal" functions, or decorate them with `@Slot(object)` for nullable parameters.

A signal-slot connection can be created (`connect()`) and destroyed (`disconenct()`) dynamically.
Every time a signal is emitted, all the slots connected to it are executed in the order they were connected.

Important considerations:
- While slots can be also anonymous lambdas, signals must be class members, therefore subclassing a QWidget is needed in case new signals are needed.
- If a slot modifies a UI element, it is possible that a new signal may be emitted, potentially causing infinite signal-slot calls. To avoid such cases, a slot should invoke `widget.blockSignals(True)` before changing its value.
- QtCreator/QtDesigner allow to directly connect signals and slots with matching signatures (e.g., `QLineEdit.textChanged(str)` and `QLabel.text(str)` will automatically copy the text from the line edit to the label) from the UI editor, this is convenient, but there is the risk of forgetting to connect something, or connecting it twice (once in the UI editor and then again in python code)

Buddies: Events involving QLabels can be redirected to different controls (e.g., clicking on a label may activate a text box on its right), to improve the user experience.
Buddies can be associated statically in `*.ui` files, or associated programmatically (e.g., when a label is created from python code).

Widget promotion: Widgets can be subclassed to provide additional functionalities, without losing the possibility of exploiting the WYSIWYG editor. It is sufficient to define a widget as belonging to a particular class, and registering at runtime the promotion.

Text masks and validators: Invalid QLineEdit input can be rejected automatically with either of two mechanisms:
- [Masks](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QLineEdit.html#PySide6.QtWidgets.QLineEdit.inputMask): force format adherence (e.g., imposing a `hh:mm:ss` format for times, or `#hhhhhh` for RGB colors) by altering the text as it is edited
- Instances of QValidator: prevent the control to emit `returnPressed` and `editingFinished` signals as long as the text entered does not pass the checks, and optionally expose methods to correct invalid text.

[Localization](https://doc.qt.io/qt-6/localization.html): Each string defined in `*.ui` files, as well as each string processed by QTranslator, `tr()` or `QCoreApplication.translate()` can be automatically extracted into an xml file by the `lupdate` tool, translated by native-language contributors, and loaded at runtime.
Since `lupdate` is a static analyzer, it is important that each string can be inspected from the source file (i.e., `tr("A static string")` will be translatable, `my_var = "A not-so-static string"; tr(my_var)` will not).

## Concurrent Execution Model
The application uses multiple approaches for concurrent execution.
- QT6 objects implicitly use the internal `QThreadPool` model. This is transparent from the programmer's perspective, but care must be taken in using Signals and Slots for every non-trivial communication mechanism
- The `ImageModel` and `BulkModel` rely on the MapReduce paradigm, therefore are implemented with a standard `multiprocessing.Pool.map` approach. Note that since it internally relies on `pickle`, not every function can be run on it (namely, class methods and lambdas are not pickleable)
- `WorkerPool` offers three execution mechanisms, all exposing the same Signal-Slot-based interface:
  1. Anonymous `QRunnable` functions automatically handled by `QThreadPool`, which can be enqueued arbitrarily many times.
  2. Named `QRunnable` functions automatically handled by `QThreadPool`, which are reentrant based on a name (if a `QRunnable` with the same name is already running, the new worker is not enqueued).
  3. Traditional `threading.Thread` functions, manually launched. This addresses two limitations of `QRunnable`, at the expenses of sacrificing automatic load balancing: exceptions in the underlying C++ code can crash the application, and the absence of `join()`.

## Decisions and Caveats
- Since the original OneTrainer code was strongly coupled with the user interface, many model classes were rewritten from scratch, with a high chance of introducing bugs.
- Enums in `modules/util/enum` have been extended with methods for GUI pretty-printing (`modules.util.enum.BaseEnum.BaseEnum` class), without altering their existing functionality
- I have more or less arbitrarily decided that strings should all be translated with `QCoreApplication.translate()`, because it groups them by context (e.g. `QCoreApplication.translate(context="model_tab", sourceText="Data Type")`), allowing explicit disambiguation every time, and providing translators with a somewhat ordered xml (every string with the same context will be close together).
- At the moment Enum values are non-translatable, because pretty printing often relies on string manipulation.
- Signal-slot connections are wrapped by `BaseController.connect()` to easily manage reconnections of dynamic widgets.
- The application exposes global signals (e.g., `modelChanged`, `openedConcept(int)`, etc.), which are used to guarantee data consistency across all UI elements, by letting slots handle updates. This should be cleaner than asking the caller to modify UI elements other than its own.
- In theory, multithreaded applications in QT6 should all use `QThread`s and pass data only via signals and slots, for efficiency (the event loop is handled automatically) and ease of debugging, however, at least for the moment I am trying to preserve the old OneTrainer approach whenever possible.
- For the time being, `modules.ui.models` classes simply handle the backend functionalities that were implemented in the old UI. In the future it may be reasonable to merge it with `modules.util.config` into thread-safe global states.
