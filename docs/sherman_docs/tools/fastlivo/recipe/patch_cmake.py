"""Fail-closed CMake edits for the inspected pinned sources, not C++ fixes."""
from pathlib import Path
import sys

PATCHES = {
    'rpg_vikit/vikit_common/CMakeLists.txt': [
        ('''IF(CMAKE_COMPILER_IS_GNUCC)
  SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x")
ELSE()
  SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
ENDIF()''', '''SET(CMAKE_CXX_STANDARD 17)
SET(CMAKE_CXX_STANDARD_REQUIRED ON)
SET(CMAKE_CXX_EXTENSIONS OFF)'''),
        ('  ${Sophus_LIBRARIES}', '  Sophus::Sophus'),
        ('# Tests\nADD_EXECUTABLE(test_vk_common_camera',
         '# Tests\nIF(BUILD_TESTING)\nADD_EXECUTABLE(test_vk_common_camera'),
        ('TARGET_LINK_LIBRARIES(test_vk_common_patch_score ${PROJECT_NAME} ${OpenCV_LIBS})',
         'TARGET_LINK_LIBRARIES(test_vk_common_patch_score ${PROJECT_NAME} ${OpenCV_LIBS})\nENDIF()'),
        # T3.5a: -march=native raises Eigen alignment to 32 bytes, while
        # Ubuntu's prebuilt PCL uses 16-byte alignment. VoxelGrid output
        # buffers then die in Eigen's handmade aligned free (teardown
        # segfault). Cap codegen at SSE3 (16-byte max), keeping the rest.
        # Fragments include the SET prefix so the fixed text is never a
        # substring of the unfixed text (fail-closed convention).
        ('SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=native -mmmx -msse -msse2 -msse3 -mssse3")',
         'SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mmmx -msse -msse2 -msse3 -mssse3")'),
    ],
    'rpg_vikit/vikit_ros/CMakeLists.txt': [
        ('  ${cpp_typesupport_target}', '  ${cpp_typesupport_target}\n  Sophus::Sophus'),
    ],
    'fast_livo/CMakeLists.txt': [
        ('set(COMMON_DEPENDENCIES OpenMP::OpenMP_CXX fmt::fmt)',
         'set(COMMON_DEPENDENCIES OpenMP::OpenMP_CXX fmt::fmt Sophus::Sophus)'),
        ('add_library(utils src/utils.cpp)',
         'add_library(utils src/utils.cpp)\ntarget_link_libraries(utils Sophus::Sophus)'),
        ('  ${Sophus_LIBRARIES}', '  Sophus::Sophus'),
        # T3.5a: same alignment fix as Vikit above; -mtune/-funroll-loops stay.
        ('set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -march=native -mtune=native -funroll-loops")',
         'set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -mtune=native -funroll-loops")'),
        # Keep the informational message honest; no codegen effect.
        ('message(STATUS "Using general x86 optimizations: -O3 -march=native -mtune=native -funroll-loops")',
         'message(STATUS "Using general x86 optimizations: -O3 -mtune=native -funroll-loops")'),
    ],
}


def transform(text: str, replacements: list[tuple[str, str]]) -> str:
    """Require exactly one occurrence of every inspected source fragment."""
    for old, new in replacements:
        if new in text:
            raise ValueError(f'Already patched fragment: {new!r}')
        count = text.count(old)
        if count != 1:
            raise ValueError(f'Expected one occurrence, got {count}: {old!r}')
        text = text.replace(old, new, 1)
    return text


def main(source: Path) -> None:
    """Validate all files before writing any transformed contents."""
    updates = [(source / name, transform((source / name).read_text(), edits))
               for name, edits in PATCHES.items()]
    for path, text in updates:
        path.write_text(text)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
