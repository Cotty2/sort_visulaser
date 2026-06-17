import random
import time
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple


Event = Dict[str, object]


# статистика выполнения сортировки
@dataclass
class SortStats:
    comparisons: int = 0
    swaps: int = 0
    writes: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def total(self) -> int:
        return self.comparisons + self.swaps + self.writes

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.perf_counter()
        return end - self.started_at


# состояние одного алгоритма
@dataclass
class SortState:
    name: str
    array: List[int]
    generator: Generator[Event, None, None]
    stats: SortStats
    done: bool = False
    last_event: Optional[Event] = None


# создание исходных массивов
def make_random_array(size: int) -> List[int]:
    return [random.randint(5, 100) for _ in range(size)]


def make_reversed_array(size: int) -> List[int]:
    return list(range(size, 0, -1))


def make_nearly_sorted_array(size: int) -> List[int]:
    arr = list(range(1, size + 1))
    swaps_count = max(1, size // 10)
    for _ in range(swaps_count):
        i = random.randint(0, size - 1)
        j = random.randint(0, size - 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


# пузырьковая сортировка
def bubble_sort(array: List[int], stats: SortStats) -> Generator[Event, None, None]:
    n = len(array)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            stats.comparisons += 1
            yield {"type": "compare", "indices": (j, j + 1)}

            if array[j] > array[j + 1]:
                array[j], array[j + 1] = array[j + 1], array[j]
                stats.swaps += 1
                stats.writes += 2
                swapped = True
                yield {"type": "swap", "indices": (j, j + 1)}

        if not swapped:
            break

    yield {"type": "done", "indices": ()}


# сортировка вставками
def insertion_sort(array: List[int], stats: SortStats) -> Generator[Event, None, None]:
    n = len(array)

    for i in range(1, n):
        key = array[i]
        j = i - 1
        yield {"type": "mark", "indices": (i,)}

        while j >= 0:
            stats.comparisons += 1
            yield {"type": "compare", "indices": (j, j + 1)}

            if array[j] > key:
                array[j + 1] = array[j]
                stats.writes += 1
                yield {"type": "write", "indices": (j + 1,)}
                j -= 1
            else:
                break

        array[j + 1] = key
        stats.writes += 1
        yield {"type": "write", "indices": (j + 1,)}

    yield {"type": "done", "indices": ()}


# сортировка слиянием
def merge_sort(array: List[int], stats: SortStats) -> Generator[Event, None, None]:
    def sort(left: int, right: int) -> Generator[Event, None, None]:
        if right - left <= 1:
            return

        mid = (left + right) // 2
        yield from sort(left, mid)
        yield from sort(mid, right)
        yield from merge(left, mid, right)

    def merge(left: int, mid: int, right: int) -> Generator[Event, None, None]:
        temp: List[int] = []
        i = left
        j = mid

        while i < mid and j < right:
            stats.comparisons += 1
            yield {"type": "compare", "indices": (i, j)}

            if array[i] <= array[j]:
                temp.append(array[i])
                i += 1
            else:
                temp.append(array[j])
                j += 1

        while i < mid:
            temp.append(array[i])
            i += 1

        while j < right:
            temp.append(array[j])
            j += 1

        for offset, value in enumerate(temp):
            array[left + offset] = value
            stats.writes += 1
            yield {"type": "write", "indices": (left + offset,)}

    yield from sort(0, len(array))
    yield {"type": "done", "indices": ()}


# быстрая сортировка
def quick_sort(array: List[int], stats: SortStats) -> Generator[Event, None, None]:
    def partition(low: int, high: int) -> Generator[Event, None, int]:
        pivot = array[high]
        pivot_index = high
        yield {"type": "pivot", "indices": (pivot_index,)}

        i = low - 1

        for j in range(low, high):
            stats.comparisons += 1
            yield {"type": "compare", "indices": (j, pivot_index)}

            if array[j] <= pivot:
                i += 1
                if i != j:
                    array[i], array[j] = array[j], array[i]
                    stats.swaps += 1
                    stats.writes += 2
                    yield {"type": "swap", "indices": (i, j)}

        if i + 1 != high:
            array[i + 1], array[high] = array[high], array[i + 1]
            stats.swaps += 1
            stats.writes += 2
            yield {"type": "swap", "indices": (i + 1, high)}

        return i + 1

    def sort(low: int, high: int) -> Generator[Event, None, None]:
        if low < high:
            pivot_pos = yield from partition(low, high)
            yield from sort(low, pivot_pos - 1)
            yield from sort(pivot_pos + 1, high)

    yield from sort(0, len(array) - 1)
    yield {"type": "done", "indices": ()}


# список доступных алгоритмов
ALGORITHMS = {
    "Пузырьковая сортировка": bubble_sort,
    "Сортировка вставками": insertion_sort,
    "Сортировка слиянием": merge_sort,
    "Быстрая сортировка": quick_sort,
}


# главное окно приложения
class SortVisualizerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Визуализатор алгоритмов сортировки")
        self.geometry("1100x750")
        self.minsize(950, 650)

        self.base_array: List[int] = []
        self.states: List[SortState] = []
        self.running = False
        self.mode = tk.StringVar(value="Один алгоритм")
        self.algorithm = tk.StringVar(value="Пузырьковая сортировка")
        self.fill_method = tk.StringVar(value="Случайный")
        self.size_var = tk.IntVar(value=35)
        self.speed_var = tk.IntVar(value=30)

        self._build_interface()
        self.base_array = []
        self.states = []
        self.update_stats_text()

    # создание элементов интерфейса
    def _build_interface(self) -> None:
        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(fill=tk.X)

        ttk.Label(control_frame, text="Режим:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Combobox(
            control_frame,
            textvariable=self.mode,
            values=["Один алгоритм", "Гонка алгоритмов"],
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(control_frame, text="Алгоритм:").grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Combobox(
            control_frame,
            textvariable=self.algorithm,
            values=list(ALGORITHMS.keys()),
            state="readonly",
            width=25,
        ).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(control_frame, text="Размер:").grid(row=0, column=4, sticky=tk.W, padx=5)
        ttk.Spinbox(control_frame, from_=5, to=120, textvariable=self.size_var, width=6).grid(
            row=0, column=5, sticky=tk.W, padx=5
        )

        ttk.Label(control_frame, text="Заполнение:").grid(row=0, column=6, sticky=tk.W, padx=5)
        ttk.Combobox(
            control_frame,
            textvariable=self.fill_method,
            values=["Случайный", "Обратный", "Почти отсортированный"],
            state="readonly",
            width=22,
        ).grid(row=0, column=7, sticky=tk.W, padx=5)

        ttk.Label(control_frame, text="Скорость:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=8)
        ttk.Scale(control_frame, from_=1, to=100, variable=self.speed_var, orient=tk.HORIZONTAL, length=170).grid(
            row=1, column=1, columnspan=2, sticky=tk.W, padx=5
        )

        ttk.Button(control_frame, text="Создать массив", command=self.generate_array).grid(
            row=1, column=3, sticky=tk.W, padx=5
        )
        ttk.Button(control_frame, text="Старт", command=self.start).grid(row=1, column=4, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="Пауза", command=self.pause).grid(row=1, column=5, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="Следующий шаг", command=self.next_step).grid(
            row=1, column=6, sticky=tk.W, padx=5
        )
        ttk.Button(control_frame, text="Сброс", command=self.reset_states).grid(row=1, column=7, sticky=tk.W, padx=5)

        self.canvas_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.stats_text = tk.Text(self, height=9, font=("Courier New", 10))
        self.stats_text.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.stats_text.configure(state=tk.DISABLED)

    # создание исходного массива
    def generate_array(self) -> None:
        try:
            size = int(self.size_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Размер массива должен быть целым числом.")
            return

        if size < 5 or size > 120:
            messagebox.showerror("Ошибка", "Размер массива должен быть от 5 до 120.")
            return

        method = self.fill_method.get()
        if method == "Случайный":
            self.base_array = make_random_array(size)
        elif method == "Обратный":
            self.base_array = make_reversed_array(size)
        else:
            self.base_array = make_nearly_sorted_array(size)

        self.reset_states()

    # сброс состояния сортировки
    def reset_states(self) -> None:
        self.running = False
        self._clear_canvases()

        if not self.base_array:
            self.states = []
            self.update_stats_text()
            return

        self.states = self._create_states()
        self._create_canvases()
        self.draw_all()
        self.update_stats_text()

    # подготовка алгоритмов к запуску
    def _create_states(self) -> List[SortState]:
        if self.mode.get() == "Гонка алгоритмов":
            names = list(ALGORITHMS.keys())
        else:
            names = [self.algorithm.get()]

        states: List[SortState] = []
        for name in names:
            arr = self.base_array.copy()
            stats = SortStats()
            gen = ALGORITHMS[name](arr, stats)
            states.append(SortState(name=name, array=arr, generator=gen, stats=stats))

        return states

    def _clear_canvases(self) -> None:
        for child in self.canvas_frame.winfo_children():
            child.destroy()

    # создание областей визуализации
    def _create_canvases(self) -> None:
        self.canvases: List[tk.Canvas] = []

        for state in self.states:
            frame = ttk.LabelFrame(self.canvas_frame, text=state.name, padding=5)
            frame.pack(fill=tk.BOTH, expand=True, pady=4)

            canvas = tk.Canvas(frame, bg="white", height=130)
            canvas.pack(fill=tk.BOTH, expand=True)
            self.canvases.append(canvas)

    # запуск автоматической сортировки
    def start(self) -> None:
        if not self.base_array:
            messagebox.showwarning("Предупреждение", "Сначала создайте массив.")
            return

        if not self.states:
            self.reset_states()

        for state in self.states:
            if state.stats.started_at is None:
                state.stats.started_at = time.perf_counter()

        self.running = True
        self._animate()

    # остановка автоматической сортировки
    def pause(self) -> None:
        self.running = False

    # выполнение одного шага
    def next_step(self) -> None:
        if not self.base_array:
            messagebox.showwarning("Предупреждение", "Сначала создайте массив.")
            return

        if not self.states:
            self.reset_states()

        for state in self.states:
            if state.stats.started_at is None:
                state.stats.started_at = time.perf_counter()

        self._perform_step()
        self.draw_all()
        self.update_stats_text()

    # цикл анимации
    def _animate(self) -> None:
        if not self.running:
            return

        active = self._perform_step()
        self.draw_all()
        self.update_stats_text()

        if active:
            delay = max(1, 105 - int(self.speed_var.get()))
            self.after(delay, self._animate)
        else:
            self.running = False

    # выполнение шага для активных алгоритмов
    def _perform_step(self) -> bool:
        active = False

        for state in self.states:
            if state.done:
                continue

            try:
                event = next(state.generator)
                state.last_event = event
                active = True

                if event.get("type") == "done":
                    state.done = True
                    state.stats.finished_at = time.perf_counter()

            except StopIteration:
                state.done = True
                state.stats.finished_at = time.perf_counter()

        return active

    # обновление всех canvas
    def draw_all(self) -> None:
        for canvas, state in zip(self.canvases, self.states):
            self._draw_array(canvas, state)

    # отрисовка одного массива
    def _draw_array(self, canvas: tk.Canvas, state: SortState) -> None:
        canvas.delete("all")
        arr = state.array
        if not arr:
            return

        width = max(canvas.winfo_width(), 800)
        height = max(canvas.winfo_height(), 120)

        max_value = max(arr)
        bar_width = max(2, width / len(arr))
        active_indices: Tuple[int, ...] = tuple(state.last_event.get("indices", ())) if state.last_event else tuple()
        event_type = state.last_event.get("type") if state.last_event else ""

        for i, value in enumerate(arr):
            x1 = i * bar_width
            x2 = x1 + bar_width - 1
            bar_height = (value / max_value) * (height - 25)
            y1 = height - bar_height
            y2 = height

            color = "#4F81BD"
            if i in active_indices:
                if event_type == "compare":
                    color = "#F1C232"
                elif event_type == "swap":
                    color = "#CC0000"
                elif event_type == "write":
                    color = "#6AA84F"
                elif event_type == "pivot":
                    color = "#8E7CC3"
                else:
                    color = "#E69138"

            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

        if state.done:
            canvas.create_text(
                width - 90,
                15,
                text="Готово",
                fill="green",
                font=("Arial", 12, "bold"),
            )

    # обновление блока статистики
    def update_stats_text(self) -> None:
        self.stats_text.configure(state=tk.NORMAL)
        self.stats_text.delete("1.0", tk.END)

        header = f"{'Алгоритм':<28} {'Сравн.':>8} {'Перест.':>8} {'Записи':>8} {'Всего':>8} {'Время, с':>10}\n"
        self.stats_text.insert(tk.END, header)
        self.stats_text.insert(tk.END, "-" * 80 + "\n")

        if not self.states:
            self.stats_text.insert(tk.END, "Массив еще не создан. Нажмите кнопку «Создать массив».\n")
            self.stats_text.configure(state=tk.DISABLED)
            return

        for state in self.states:
            line = (
                f"{state.name:<28} "
                f"{state.stats.comparisons:>8} "
                f"{state.stats.swaps:>8} "
                f"{state.stats.writes:>8} "
                f"{state.stats.total:>8} "
                f"{state.stats.elapsed:>10.3f}\n"
            )
            self.stats_text.insert(tk.END, line)

        self.stats_text.configure(state=tk.DISABLED)


if __name__ == "__main__":
    app = SortVisualizerApp()
    app.mainloop()
